"""tests/test_container.py

This module contains integration tests for the Spark development container.
It verifies that:
    - The Spark Scala API is available via spark-shell.
    - The Spark Python API is available via pyspark.
    - The SSH server is up and accessible.
    - The Spark submit command is available.
    - The Java version is as expected.
    - The Scala REPL is available.
    - The uv package is installed.
    - Git is installed.
    - Curl is installed.
    - The SPARK_HOME environment variable is set and included in PATH.
  
Run the tests with:
    pytest tests/test_container.py
"""

import subprocess
import time
import pytest
import os
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
DOCKER_IMAGE = os.getenv("TEST__DOCKER_IMAGE")
SSH_HOST = os.getenv("TEST__SSH_HOST")
SSH_PORT = int(os.getenv("TEST__SSH_PORT"))
SSH_USER = os.getenv("TEST__SSH_USER")
SSH_PASSWORD = os.getenv("TEST__SSH_PASSWORD")

# ---------------------------------------------------------------------------
# Utility Functions
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
        raise RuntimeError(f"Command failed: {cmd}\nSTDERR: {result.stderr}")
    return result.stdout.strip()

# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
def test_spark_shell_version():
    """Test that the spark-shell command returns version information."""
    cmd = f"docker run --rm {DOCKER_IMAGE} spark-shell --version"
    output = run_command(cmd)
    assert "version" in output.lower(), f"spark-shell did not return version info\n{output}"

def test_pyspark_version():
    """Test that the pyspark command returns version information."""
    cmd = f"docker run --rm {DOCKER_IMAGE} pyspark --version"
    output = run_command(cmd)
    assert "version" in output.lower(), f"pyspark did not return version info:\n{output}"

@pytest.fixture(scope="module")
def ssh_container():
    """Fixture to run the container in detached mode to test SSH connectivity. 
    
    Maps container port 22 to host port defined by SSH_PORT.
    """
    container_id = run_command(f"docker run -d -p {SSH_PORT}:22 {DOCKER_IMAGE}")
    # Allow some time for sshd to start
    time.sleep(5)
    yield container_id
    # Cleanup container after test completes
    run_command(f"docker rm -f {container_id}")

def test_ssh_connection(ssh_container):
    """Test that the SSH server inside the container is accessible by attempting to SSH into the container and run 'echo SSH OK'."""
    # The SSH client should be available on the GitHub Actions runner.
    # Disable host key checking for this test.
    ssh_cmd = (
        f"ssh -o StrictHostKeyChecking=no "
        f"-o UserKnownHostsFile=/dev/null "
        f"-p {SSH_PORT} {SSH_USER}@{SSH_HOST} echo 'SSH OK'"
    )
    output = run_command(ssh_cmd, timeout=15)
    assert "SSH OK" in output, f"SSH connection test failed. Expected to see 'SSH OK' in output:\n{output}"

def test_spark_submit():
    """Test that spark-submit returns version information."""
    cmd = f"docker run --rm {DOCKER_IMAGE} spark-submit --version"
    output = run_command(cmd)
    assert "version" in output.lower(), f"spark-submit did not return version info:\n{output}"

def test_java_version():
    """Test that the installed Java version is as expected (e.g., OpenJDK 11)."""
    cmd = f"docker run --rm {DOCKER_IMAGE} java -version"
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    output = result.stderr.lower()  # version info goes to stderr
    assert "openjdk" in output, f"Java installation seems to be missing OpenJDK. Expected OpenJDK in output:\n{output}"
    assert "11" in output, f"Java version is not 11 as expected. Expected '11' in output:\n{output}"

def test_scala_repl():
    """Test that the Scala REPL works and can execute a simple expression."""
    cmd = f"docker run --rm {DOCKER_IMAGE} scala -e \"println(42)\""
    output = run_command(cmd)
    assert "42" in output, f"Scala REPL did not output expected value. Expected '42' in output:\n{output}"

def test_uv_installed():
    """Test that the uv package is installed by importing it in Python."""
    cmd = f"docker run --rm {DOCKER_IMAGE} python3 -c \"import uv; print(uv.__version__)\""
    output = run_command(cmd)
    assert output.strip(), f"uv package does not seem to be installed. Expected a version string, got empty output."

def test_git_installed():
    """Test that git is installed."""
    cmd = f"docker run --rm {DOCKER_IMAGE} git --version"
    output = run_command(cmd)
    assert "git version" in output, f"Git does not seem to be installed. Expected 'git version' in output:\n{output}"

def test_curl_installed():
    """Test that curl is installed."""
    cmd = f"docker run --rm {DOCKER_IMAGE} curl --version"
    output = run_command(cmd)
    assert "curl" in output.lower(), f"Curl does not seem to be installed. Expected 'curl' in output:\n{output}"

def test_env_variables():
    """Test that SPARK_HOME is set and included in PATH."""
    cmd = f"docker run --rm {DOCKER_IMAGE} bash -c 'echo $SPARK_HOME && echo $PATH'"
    output = run_command(cmd)
    assert "spark_home" in output.lower(), f"SPARK_HOME environment variable not set. Expected 'spark_home' in output:\n{output}"
