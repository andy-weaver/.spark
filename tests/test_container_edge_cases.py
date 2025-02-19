"""tests/test_container_edge_cases.py

This module contains tests to validate edge cases in the Spark development Docker
container. It covers delayed service startups, network connectivity, resource constraints,
port conflicts, TTY vs. non-TTY behavior, environment variable overrides, file system
permissions, container logs, user permissions, and a minimal Spark job execution.

Run the tests with:
    pytest tests/test_container_edge_cases.py
"""

import subprocess
import time
import socket
import pytest
import os
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Global Constants
# ---------------------------------------------------------------------------
DOCKER_IMAGE = os.getenv("TEST__DOCKER_IMAGE")
SSH_HOST = os.getenv("TEST__SSH_HOST")
SSH_PORT = int(os.getenv("TEST__SSH_PORT"))
SSH_USER = os.getenv("TEST__SSH_USER")
SSH_PASSWORD = os.getenv("TEST__SSH_PASSWORD")

# ---------------------------------------------------------------------------
# Utility Function
# ---------------------------------------------------------------------------
def run_command(cmd, timeout=30):
    """Run a shell command and return its stdout as a string.

    Parameters
    ----------
    cmd : str
        The shell command to run.
    timeout : int, optional
        Timeout in seconds (default is 30).

    Returns
    -------
    str
        Standard output from the command.

    Raises
    ------
    RuntimeError
        If the command exits with a non-zero status.
    """
    result = subprocess.run(
        cmd, shell=True, capture_output=True, text=True, timeout=timeout
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"Command failed: {cmd}\nSTDOUT: {result.stdout}\nSTDERR: {result.stderr}"
        )
    return result.stdout.strip()

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def ssh_container():
    """Fixture to run the container in detached mode with SSH mapping.

    Maps container port 22 to host port SSH_PORT.
    """
    container_id = run_command(f"docker run -d -p {SSH_PORT}:22 {DOCKER_IMAGE}")
    # Allow time for sshd to start.
    time.sleep(5)
    yield container_id
    run_command(f"docker rm -f {container_id}")

@pytest.fixture(scope="function")
def detached_container():
    """Fixture to run the container in detached mode (for logs and other tests)."""
    container_id = run_command(f"docker run -d -p {SSH_PORT}:22 {DOCKER_IMAGE}")
    # Give a moment for startup messages.
    time.sleep(3)
    yield container_id
    run_command(f"docker rm -f {container_id}")

# ---------------------------------------------------------------------------
# Test Cases
# ---------------------------------------------------------------------------
def test_ssh_service_delayed(ssh_container):
    """Test SSH readiness with retries to handle potential delayed startup.

    The test attempts to SSH into the container multiple times until a successful
    "SSH_READY" message is returned.
    """
    max_attempts = 5
    for attempt in range(max_attempts):
        try:
            cmd = (
                f"ssh -o BatchMode=yes -o StrictHostKeyChecking=no "
                f"-o UserKnownHostsFile=/dev/null -o ConnectTimeout=5 "
                f"-p {SSH_PORT} {SSH_USER}@{SSH_HOST} echo SSH_READY"
            )
            output = run_command(cmd, timeout=10)
            assert "SSH_READY" in output, "Did not receive expected SSH readiness message."
            break
        except Exception as e:
            if attempt == max_attempts - 1:
                pytest.fail(
                    f"SSH service did not become ready after {max_attempts} attempts. Error: {e}"
                )
            time.sleep(2)


def test_network_connectivity():
    """Test that the container can access external network resources via curl.

    This test fetches https://example.com and checks for the known 'Example Domain' text.
    """
    cmd = f"docker run --rm {DOCKER_IMAGE} curl -s https://example.com"
    output = run_command(cmd, timeout=20)
    assert "Example Domain" in output, "Failed to fetch expected content from example.com."


def test_resource_constraint():
    """Test that the container runs correctly under memory constraints.

    The container is run with a memory limit (256MB) while executing 'java -version'
    to verify that even under constrained resources, critical commands succeed.
    """
    cmd = f"docker run --rm --memory=256m {DOCKER_IMAGE} java -version"
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, "Container did not run correctly under memory constraints."


def test_port_conflict():
    """Test that attempting to map a host port already in use causes a failure.

    This test binds a socket to SSH_PORT on the host, then tries to run the container
    mapping the same port. The expectation is that Docker fails with a port-binding error.
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("localhost", SSH_PORT))
    sock.listen(1)
    with pytest.raises(RuntimeError) as excinfo:
        run_command(f"docker run --rm -p {SSH_PORT}:22 {DOCKER_IMAGE} sleep 1", timeout=10)
    sock.close()
    error_msg = str(excinfo.value).lower()
    assert (
        "address already in use" in error_msg or "bind" in error_msg
    ), "Port conflict did not produce the expected error."


def test_non_interactive_vs_tty():
    """Test that spark-shell returns version information in both TTY and non-TTY modes.

    This verifies that interactive and non-interactive usage yield expected outputs.
    """
    cmd_non_tty = f"docker run --rm {DOCKER_IMAGE} spark-shell --version"
    output_non_tty = run_command(cmd_non_tty)
    cmd_tty = f"docker run --rm -t {DOCKER_IMAGE} spark-shell --version"
    output_tty = run_command(cmd_tty)
    assert "version" in output_non_tty.lower(), "Non-TTY spark-shell output did not contain version info."
    assert "version" in output_tty.lower(), "TTY spark-shell output did not contain version info."


def test_override_env_variable():
    """Test that environment variables can be overridden at container runtime.

    Here we override SPARK_HOME and verify that the new value is in effect.
    """
    override_value = "/override/path"
    cmd = (
        f"docker run --rm -e SPARK_HOME={override_value} {DOCKER_IMAGE} "
        f"bash -c 'echo $SPARK_HOME'"
    )
    output = run_command(cmd)
    assert output.strip() == override_value, "Environment variable override did not work as expected."


def test_filesystem_permissions():
    """Test that the file system permissions for /opt are correctly set and contain the Spark installation.

    It checks that /opt is readable and that a Spark installation directory is present.
    """
    cmd = f"docker run --rm {DOCKER_IMAGE} ls -ld /opt"
    output = run_command(cmd)
    assert output.startswith("drwx"), "Directory /opt does not have expected permissions."
    # Verify that a directory with 'spark' in its name exists under /opt.
    cmd_spark = f"docker run --rm {DOCKER_IMAGE} bash -c 'ls /opt | grep -i spark'"
    output_spark = run_command(cmd_spark)
    assert "spark" in output_spark.lower(), "Spark installation not found in /opt."


def test_container_logs(detached_container):
    """Test that container logs contain expected startup messages and are free of critical errors.

    The test checks that sshd (or similar) startup messages appear and that no severe error
    indicators are present in the logs.
    """
    logs = run_command(f"docker logs {detached_container}")
    assert "sshd" in logs.lower(), "Container logs do not contain expected sshd startup message."
    # Optionally, check that logs do not contain obvious error indicators.
    error_indicators = ["fatal", "error", "exception"]
    for indicator in error_indicators:
        assert indicator not in logs.lower(), f"Container logs contain potential error indicator: {indicator}"


def test_running_as_root():
    """Test that the container is running as the root user.

    This confirms that the default user inside the container has UID 0.
    """
    cmd = f"docker run --rm {DOCKER_IMAGE} id -u"
    output = run_command(cmd)
    assert output.strip() == "0", "Container is not running as root."


def test_spark_submit_job():
    """Test that a simple Spark job executes successfully using spark-submit.

    A minimal Python Spark job is created on the fly and executed; the output is checked
    for an expected message.
    """
    # The job prints a message to standard output.
    job_script = "print('Hello, Spark!')"
    # Note: We use bash to create a temporary file and then run spark-submit.
    cmd = (
        f"docker run --rm {DOCKER_IMAGE} bash -c "
        f"\"echo '{job_script}' > /tmp/test.py && spark-submit /tmp/test.py\""
    )
    output = run_command(cmd, timeout=60)
    assert "Hello, Spark!" in output, "Spark job did not produce expected output."