#!/bin/bash
# -----------------------------------------------------------------------
# DATAPROC 2.2 (DEBIAN 12) INITIALIZATION SCRIPT - CLEAN NETWORK
# -----------------------------------------------------------------------

# 1. Config Java
echo "Configuring Java..."
cat <<EOF | sudo tee /etc/profile.d/flink_java_opts.sh
export _JAVA_OPTIONS="--add-opens=java.base/java.net=ALL-UNNAMED --add-opens=java.base/java.util=ALL-UNNAMED --add-opens=java.base/java.lang=ALL-UNNAMED --add-opens=java.base/java.lang.reflect=ALL-UNNAMED --add-opens=java.base/sun.security.ssl=ALL-UNNAMED"
EOF
source /etc/profile.d/flink_java_opts.sh

# 2. Install python and libraries
echo "Installing Python packages..."
sudo apt-get update
sudo apt-get install -y python3-pip net-tools
pip3 install --upgrade pip
pip3 install "setuptools<70" "apache-flink==1.17.2" "six" "pandas"

# 3. Auto write jars to Flink
echo "Downloading Flink Connectors from GCS..."
sudo gsutil -m cp gs://crypto-raw-archive-unique-6451/flink-jars/*.jar /usr/lib/flink/lib/ || true

# 4. Create folder for Flink Job
echo "Setting up workspace..."
mkdir -p /tmp/flink_job
chmod 777 /tmp/flink_job
