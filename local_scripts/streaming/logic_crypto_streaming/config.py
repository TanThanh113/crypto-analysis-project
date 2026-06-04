import os


# 1. FLINK & KAFKA CONFIGURATION
KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP", "localhost:9092")
KAFKA_GROUP_ID = os.getenv("KAFKA_GROUP_ID", "flink_crypto_main_group")

# 2. GOOGLE CLOUD PLATFORM
PROJECT_ID = "project-lambda-crypto"
DATASET_ID = "crypto_analytics_dataset"
BUCKET_NAME = "crypto-raw-archive-unique-6451"

# 3. KAFKA TOPICS (SOURCES - FLINK In)
TOPIC_TRADES = "crypto_trades"
TOPIC_ORDERBOOK = "crypto_orderbook"
TOPIC_LIQUIDATIONS = "crypto_liquidations"
TOPIC_SENTIMENT = "crypto_sentiment"
TOPIC_ONCHAIN = "crypto_onchain_alerts"

# 4. KAFKA TOPICS (SINKS - FLINK Out)
TOPIC_ALERTS_OUTPUT = "processed_alerts"
TOPIC_RAW_CANDLESTICK = "processed_candlestick_1min"
