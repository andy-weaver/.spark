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
# To run (and expose SSH on port 2222 for example):
#   docker run -d -p 2222:22 spark-dev
#
# SSH into the container with:
#   ssh root@localhost -p 2222
#   (password is "root")
# -----------------------------------------------------------------------------

FROM ubuntu:20.04

# Avoid interactive prompts during build
ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies
RUN apt-get update && apt-get install -y \
    openjdk-11-jdk \
    python3 \
    python3-pip \
    scala \
    git \
    curl \
    openssh-server \
    vim \
    && rm -rf /var/lib/apt/lists/*

# Install uv as the Python package manager
RUN pip3 install uv

# Install Apache Spark (version 3.3.1 with Hadoop 3 support)
ENV SPARK_VERSION=3.3.1
ENV HADOOP_VERSION=3
ENV SPARK_PACKAGE=spark-${SPARK_VERSION}-bin-hadoop${HADOOP_VERSION}
RUN curl -fSL "https://archive.apache.org/dist/spark/spark-${SPARK_VERSION}/${SPARK_PACKAGE}.tgz" -o /tmp/spark.tgz \
    && tar -xzf /tmp/spark.tgz -C /opt/ \
    && rm /tmp/spark.tgz
ENV SPARK_HOME=/opt/${SPARK_PACKAGE}
ENV PATH=$PATH:$SPARK_HOME/bin:$SPARK_HOME/sbin

# Configure SSH
RUN mkdir /var/run/sshd \
    && echo 'root:root' | chpasswd \
    && sed -i 's/#PermitRootLogin prohibit-password/PermitRootLogin yes/' /etc/ssh/sshd_config \
    && sed -i 's/PermitRootLogin prohibit-password/PermitRootLogin yes/' /etc/ssh/sshd_config

# Expose SSH port
EXPOSE 22

# Default command: run SSH server in the foreground
CMD ["/usr/sbin/sshd", "-D"]
