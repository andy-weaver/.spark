# -----------------------------------------------------------------------------
# Dockerfile for Spark Development Container
#
# This container provides:
#   - OpenJDK 11 (for Spark)
#   - Python 3 and pip (with uv installed as the Python package manager)
#   - Scala (for using the Spark Scala API, e.g. spark-shell)
#   - Apache Spark (downloaded and configured with both Python and Scala APIs)
#   - Git and curl
#   - OpenSSH server (so you can SSH in with an IDE)
#
# To build:
#   docker build -t spark-dev .
#
# SSH into the container with:
#   ssh root@localhost -p 2222
#   (password is "root")
# -----------------------------------------------------------------------------

FROM apache/spark:3.5.4-scala2.12-java17-python3-r-ubuntu

# Avoid interactive prompts during build
ENV DEBIAN_FRONTEND=noninteractive

# Install as root
USER root

# Set the working directory to /app
WORKDIR /app

# Copy the pyproject.toml and .python-version files to the container
COPY pyproject.toml /app/pyproject.toml
COPY .python-version /app/.python-version
COPY .gitignore /app/.gitignore

# Install system dependencies
RUN apt-get update && \
    apt-get install -y \
        openjdk-11-jdk \
        python3 \
        python3-pip \
        scala \
        git \
        curl \
        openssh-server \
        vim \
        zsh \
        wget && \
    rm -rf /var/lib/apt/lists/*

# Install uv as the Python package manager
RUN pip3 install uv

# Set up the Python environment
RUN python3 -m uv sync

# Configure SSH
RUN mkdir /var/run/sshd \
    && echo 'root:root' | chpasswd \
    && sed -i 's/#PermitRootLogin prohibit-password/PermitRootLogin yes/' /etc/ssh/sshd_config \
    && sed -i 's/PermitRootLogin prohibit-password/PermitRootLogin yes/' /etc/ssh/sshd_config

# Generate SSH keys
RUN ssh-keygen -A

# Expose SSH port
EXPOSE 22

# Set up the Spark environment
ENV SPARK_HOME=/opt/spark
ENV JAVA_HOME=/opt/java/openjdk
ENV PATH=$SPARK_HOME/bin:$SPARK_HOME/sbin:$PATH

# Clean up
RUN apt-get clean && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# Set up the Spark environment
RUN SPARK_DIR=$(find / -type d -name "spark-*" 2>/dev/null | head -n 1) && \
    echo "export SPARK_HOME=$SPARK_DIR" >> /etc/profile && \
    echo "export PATH=$SPARK_HOME/bin:$SPARK_HOME/sbin:$PATH" >> /etc/profile && \
    echo "export PATH=/opt/spark/bin:/opt/spark/sbin:$PATH" >> /etc/profile

# Set the default shell to zsh
RUN chsh -s /usr/bin/zsh root && \
    echo "export PATH=$PATH" >> /root/.zshrc && \
    echo "export SPARK_HOME=/opt/spark" >> /root/.zshrc && \
    echo "export JAVA_HOME=/opt/java/openjdk" >> /root/.zshrc

# Set the default shell to zsh
SHELL ["/usr/bin/zsh", "-c"]


# Default command: run SSH server in the foreground
CMD ["/usr/sbin/sshd", "-D"]
