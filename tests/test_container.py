"""
tests/test_container.py

This module contains integration tests for the Spark development container.
It verifies that:
  - The Spark Scala API is available via spark-shell.
  - The Spark Python API is available via pyspark.
  - The SSH server is up and accessible.
  
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
# Note: This image name must match the one built in the GitHub Action.
DOCKER_IMAGE = os.getenv("DOCKER_IMAGE") #"spark:test"
SSH_HOST = os.getenv("SSH_HOST") # "localhost"
SSH_PORT = int(os.getenv("SSH_PORT")) # 2222
SSH_USER = os.getenv("SSH_USER") # "root"
SSH_PASSWORD = os.getenv("SSH_PASSWORD") # "root"

# ---------------------------------------------------------------------------
# Utility Functions
# ---------------------------------------------------------------------------
def run_command(cmd, timeout=30):
    """
    Run a shell command and return its stdout as a string.

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
    """
    Test that the spark-shell command returns version information.
    """
    cmd = f"docker run --rm {DOCKER_IMAGE} spark-shell --version"
    output = run_command(cmd)
    assert "version" in output.lower(), "spark-shell did not return version info."

def test_pyspark_version():
    """
    Test that the pyspark command returns version information.
    """
    cmd = f"docker run --rm {DOCKER_IMAGE} pyspark --version"
    output = run_command(cmd)
    assert "version" in output.lower(), "pyspark did not return version info."

@pytest.fixture(scope="module")
def ssh_container():
    """
    Fixture to run the container in detached mode to test SSH connectivity.
    Maps container port 22 to host port defined by SSH_PORT.
    """
    container_id = run_command(f"docker run -d -p {SSH_PORT}:22 {DOCKER_IMAGE}")
    # Allow some time for sshd to start
    time.sleep(5)
    yield container_id
    # Cleanup container after test completes
    run_command(f"docker rm -f {container_id}")

def test_ssh_connection(ssh_container):
    """
    Test that the SSH server inside the container is accessible.
    
    It attempts to SSH into the container and run 'echo SSH OK'.
    """
    # The SSH client should be available on the GitHub Actions runner.
    # We disable host key checking for this test.
    ssh_cmd = (
        f"ssh -o StrictHostKeyChecking=no "
        f"-o UserKnownHostsFile=/dev/null "
        f"-p {SSH_PORT} {SSH_USER}@{SSH_HOST} echo 'SSH OK'"
    )
    output = run_command(ssh_cmd, timeout=15)
    assert "SSH OK" in output, "SSH connection test failed."
