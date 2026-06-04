#!/bin/bash

set -e

trap 'rm -f ./temp_remote_script.sh' EXIT

CLUSTER_NAME="crypto-streaming-cluster"
ZONE="asia-southeast1-c"

source .env

echo "🚀 Deploy the ULTRA STABLE version. - MÁY 32GB 🚀"
echo "🔗 Kafka bootstrap from .env: ${KAFKA_ADVERTISED_ADDR}"

cat << EOF > ./temp_remote_script.sh
#!/bin/bash

set -e

export HADOOP_CLASSPATH=\$(hadoop classpath)
export KAFKA_BOOTSTRAP="${KAFKA_ADVERTISED_ADDR}"

echo "🔗 Using Kafka bootstrap: \$KAFKA_BOOTSTRAP"

echo "🧹 Clean up config..."
sudo sed -i '/taskmanager.memory/d; /jobmanager.memory/d; /env.java.opts/d; /heartbeat/d; /execution.checkpointing/d; /state.backend/d' /etc/flink/conf/flink-conf.yaml

echo "💎 Record optimal configuration..."

sudo tee -a /etc/flink/conf/flink-conf.yaml > /dev/null <<YAML
# --- RAM 32GB Configuration ---
taskmanager.memory.process.size: 20480m
jobmanager.memory.process.size: 2048m
taskmanager.memory.task.off-heap.size: 6144m
taskmanager.memory.managed.fraction: 0.1
taskmanager.numberOfTaskSlots: 4

env.java.opts.all: --add-opens=java.base/java.net=ALL-UNNAMED --add-opens=java.base/java.util=ALL-UNNAMED --add-opens=java.base/java.lang=ALL-UNNAMED --add-opens=java.base/java.lang.reflect=ALL-UNNAMED --add-opens=java.base/sun.security.ssl=ALL-UNNAMED

# --- Stability ---
state.backend: rocksdb
state.backend.incremental: true
execution.checkpointing.interval: 30s
execution.checkpointing.timeout: 120000
execution.checkpointing.min-pause: 10000
execution.checkpointing.max-concurrent-checkpoints: 1
heartbeat.timeout: 180000
heartbeat.interval: 20000
YAML

echo "📦 Packing dependencies..."
cd /tmp/flink_job
rm -f dependencies.zip
zip -r dependencies.zip . -x "main.py" -x "*__pycache__*"

echo "🔥 Executing Job..."
flink run -m yarn-cluster -d \
    -p 1 \
    -ys 4 \
    -yjm 2048m \
    -ytm 20480m \
    -yD taskmanager.memory.task.off-heap.size=6144m \
    -py /tmp/flink_job/main.py \
    -pyfs /tmp/flink_job/dependencies.zip
EOF

echo "📤 Uploading remote deploy script to Dataproc..."
gcloud compute scp ./temp_remote_script.sh ${CLUSTER_NAME}-m:/tmp/remote_deploy.sh \
  --zone=${ZONE} \
  --tunnel-through-iap

echo "🚀 Running remote deploy script..."
gcloud compute ssh ${CLUSTER_NAME}-m \
  --zone=${ZONE} \
  --tunnel-through-iap \
  --command="bash /tmp/remote_deploy.sh"

rm ./temp_remote_script.sh