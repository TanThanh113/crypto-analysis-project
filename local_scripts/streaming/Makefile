CLUSTER_NAME=crypto-streaming-cluster
ZONE=asia-southeast1-c

LOCAL_PATH=.
LOCAL_PYTHON_DIR=$(LOCAL_PATH)/logic_crypto_streaming
CONFIG_FILE=$(LOCAL_PYTHON_DIR)/config.py
PRODUCER_DIR=$(LOCAL_PATH)/producer

DOCKER_COMPOSE_FILE=$(LOCAL_PATH)/docker-compose.yaml

# ----------------------------------------------------------------------
# 1. CORE INFRASTRUCTURE TARGETS
# ----------------------------------------------------------------------

up: tunnel_local update_config restart_redpanda setup_kafka_connect sync deploy
	@echo "🚀 Flink job & Kafka Connect deployed successfully!"
run: sync deploy
	@echo "🚀 Flink job deployed successfully!"
tunnel_local:
	@echo "📡 Opening Ngrok TCP Tunnel on Local..."
	@rm -f /tmp/ngrok.log
	@nohup ngrok tcp 9092 > /tmp/ngrok.log 2>&1 &
	@echo "⏳ Waiting for Ngrok to start (5s)..."
	@sleep 5

update_config:
	@echo "🔗 Retrieving the latest Ngrok URL..."
	$(eval NGROK_URL=$(shell curl -s http://localhost:4040/api/tunnels | jq -r '.tunnels[0].public_url' | sed 's/tcp:\/\///'))
	@if [ -z "$(NGROK_URL)" ] || [ "$(NGROK_URL)" = "null" ]; then echo "❌ Error: Could not retrieve Ngrok URL! Check if Ngrok is running."; exit 1; fi
	@echo "🎉 New Ngook URL: $(NGROK_URL)"
	
	@echo "📝 Write to the .env file so Redpanda can recognize it...."
	@echo "KAFKA_ADVERTISED_ADDR=$(NGROK_URL)" > .env
	@echo "KAFKA_BROKER=$(NGROK_URL)" >> .env

restart_redpanda:
	@echo "♻️ Restarting Redpanda & Kafka Connect..."
	@docker-compose down && docker-compose up -d
	@echo "⏳ Waiting for services to be fully ready (25s)..."
	@sleep 25

setup_kafka_connect:
	@echo "🔌 Waiting for Kafka Connect to fully boot up. (30s)..."
	@sleep 30
	@echo "🔌 Load BigQuery Sink configuration for Alerts..."
	@curl -s -X PUT http://localhost:8083/connectors/bq-alerts-sink/config \
	  -H "Content-Type: application/json" \
	  -d @scripts/bq_alerts_sink.json || true
	@echo "\n🔌 Load BigQuery Sink configuration for Candlesticks..."
	@curl -s -X PUT http://localhost:8083/connectors/bq-candlestick-sink/config \
	  -H "Content-Type: application/json" \
	  -d @scripts/bq_candlestick_sink.json || true
	@echo "\n🔌 Load BigQuery Sink configuration for Sentiment & Macro Metrics..."
	@curl -s -X PUT http://localhost:8083/connectors/bq-sentiment-sink/config \
	  -H "Content-Type: application/json" \
	  -d @scripts/bq_sentiment_sink.json || true
	@echo "\n✅ Kafka Connect configuration completed."

sync:
	@echo "📂 Syncing updated code to Dataproc..."
	@gcloud compute ssh $(CLUSTER_NAME)-m --zone=$(ZONE) --tunnel-through-iap --command="sudo rm -rf /tmp/flink_job && mkdir -p /tmp/flink_job && sudo chmod 777 /tmp/flink_job"
	@gcloud compute scp --recurse $(LOCAL_PYTHON_DIR)/* $(CLUSTER_NAME)-m:/tmp/flink_job/ --zone=$(ZONE) --tunnel-through-iap
	@echo "✅ Synced updated code to Dataproc."

deploy:
	@echo "🚀 Deploying Flink job to Dataproc..."
	@./scripts/deploy_flink.sh

# ----------------------------------------------------------------------
# 2. PYTHON PRODUCERS (BOTS) MANAGEMENT
# ----------------------------------------------------------------------

start_bots:
	@echo "🤖 Starting all Crypto Producers in background..."
	@mkdir -p logs
	@nohup uv run $(PRODUCER_DIR)/binance_full_producer.py > logs/binance.log 2>&1 & echo $$! > logs/binance.pid
	@nohup uv run $(PRODUCER_DIR)/onchain_producer.py > logs/onchain.log 2>&1 & echo $$! > logs/onchain.pid
	@nohup uv run $(PRODUCER_DIR)/sentiment_producer.py > logs/sentiment.log 2>&1 & echo $$! > logs/sentiment.pid
	@echo "✅ All bots are running! Use 'make log_binance', 'make log_onchain', or 'make log_sentiment' to view logs."

stop_bots:
	@echo "🛑 Stopping all Crypto Producers..."
	@-kill `cat logs/binance.pid` 2>/dev/null || true
	@-kill `cat logs/onchain.pid` 2>/dev/null || true
	@-kill `cat logs/sentiment.pid` 2>/dev/null || true
	@rm -f logs/*.pid
	@echo "✅ All bots stopped."

# ----------------------------------------------------------------------
# 3. LOG VIEWERS (TAIL BOTS)
# ----------------------------------------------------------------------

log_binance:
	@tail -f logs/binance.log

log_onchain:
	@tail -f logs/onchain.log

log_sentiment:
	@tail -f logs/sentiment.log

# ----------------------------------------------------------------------
# 4. TEARDOWN
# ----------------------------------------------------------------------
clean_tmp:
	@echo "🧹 Cleaning temporary deploy files..."
	@rm -f temp_remote_script.sh
	@rm -f ./scripts/temp_remote_script.sh
	@-gcloud compute ssh $(CLUSTER_NAME)-m \
		--zone=$(ZONE) \
		--tunnel-through-iap \
		--command="rm -f /tmp/remote_deploy.sh && sudo rm -rf /tmp/flink_job" 2>/dev/null || true
	@echo "✅ Temporary files cleaned."

down: stop_bots clean_tmp
	@echo "🛑 Stopping Ngrok and Docker..."
	@-pkill -f "ngrok tcp 9092" 2>/dev/null || true
	@rm -f /tmp/ngrok.log
	@rm -f .env
	@docker-compose -f $(DOCKER_COMPOSE_FILE) down --remove-orphans
	@echo "✅ Local streaming stack stopped and cleaned."