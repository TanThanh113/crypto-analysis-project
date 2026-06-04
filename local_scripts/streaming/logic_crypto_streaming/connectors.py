# -*- coding: utf-8 -*-
from config import *

# ==============================================================================
# 0. THIẾT LẬP ICEBERG CATALOG (Nền tảng cho Lakehouse)
# ==============================================================================

def setup_iceberg_catalog(table_env):
    """Khởi tạo Catalog để quản lý các bảng Iceberg trên GCS"""
    catalog_name = "iceberg_catalog"
    table_env.execute_sql(f"""
        CREATE CATALOG {catalog_name} WITH (
            'type'='iceberg',
            'catalog-type'='hadoop',
            'warehouse'='gs://{BUCKET_NAME}/iceberg_warehouse',
            'property-version'='1'
        )
    """)
    
    # Tạo database trực tiếp bên trong catalog iceberg
    table_env.execute_sql(f"CREATE DATABASE IF NOT EXISTS {catalog_name}.iceberg_db")
    
    # QUAN TRỌNG: Ép Flink quay về catalog mặc định trong RAM 
    # để các bảng Kafka không bị lưu nhầm vào Iceberg!
    table_env.execute_sql("USE CATALOG default_catalog")
    
    return catalog_name

# ==============================================================================
# SOURCERS: 5 Data extraction nozzles from KAFKA to FLINK.
# ==============================================================================

# Create Kafka connector
def create_trade_source(table_env):
    table_name = "source_trades"
    table_env.execute_sql(f"""
        CREATE TABLE {table_name} (
            symbol STRING,
            trade_id BIGINT,
            price DOUBLE,
            quantity DOUBLE,
            event_time BIGINT,
            trade_time BIGINT,
            trade_ts AS TO_TIMESTAMP_LTZ(trade_time, 3),
            WATERMARK FOR trade_ts AS trade_ts - INTERVAL '2' SECOND
        ) WITH (
            'connector' = 'kafka',
            'topic' = '{TOPIC_TRADES}',
            'properties.bootstrap.servers' = '{KAFKA_BOOTSTRAP}',
            'properties.group.id' = '{KAFKA_GROUP_ID}',
            'format' = 'json',
            'json.ignore-parse-errors' = 'true',
            'scan.startup.mode' = 'latest-offset'
        )
    """)
    return table_name

def create_orderbook_source(table_env):
    table_name = "source_orderbook"
    table_env.execute_sql(f"""
        CREATE TABLE {table_name} (
            symbol STRING,
            best_bid_price DOUBLE,
            best_ask_price DOUBLE,
            best_bid_qty DOUBLE,
            best_ask_qty DOUBLE,
            bid_vol_1pct_usd DOUBLE,
            ask_vol_1pct_usd DOUBLE,
            imbalance_ratio DOUBLE,
            event_time BIGINT,
            ob_ts AS TO_TIMESTAMP_LTZ(event_time, 3),
            WATERMARK FOR ob_ts AS ob_ts - INTERVAL '2' SECOND
        ) WITH (
            'connector' = 'kafka',
            'topic' = '{TOPIC_ORDERBOOK}',
            'properties.bootstrap.servers' = '{KAFKA_BOOTSTRAP}',
            'properties.group.id' = '{KAFKA_GROUP_ID}',
            'format' = 'json',
            'json.ignore-parse-errors' = 'true',
            'scan.startup.mode' = 'latest-offset'
        )
    """)
    return table_name

def create_liquidation_source(table_env):
    table_name = "source_liquidations"
    table_env.execute_sql(f"""
        CREATE TABLE {table_name} (
            symbol STRING,
            side STRING,
            price DOUBLE,
            quantity DOUBLE,
            event_time BIGINT,
            liq_ts AS TO_TIMESTAMP_LTZ(event_time, 3),
            WATERMARK FOR liq_ts AS liq_ts - INTERVAL '2' SECOND
        ) WITH (
            'connector' = 'kafka',
            'topic' = '{TOPIC_LIQUIDATIONS}',
            'properties.bootstrap.servers' = '{KAFKA_BOOTSTRAP}',
            'properties.group.id' = '{KAFKA_GROUP_ID}',
            'format' = 'json',
            'json.ignore-parse-errors' = 'true',
            'scan.startup.mode' = 'latest-offset'
        )
    """)
    return table_name

def create_sentiment_source(table_env):
    table_name = "source_sentiment"
    table_env.execute_sql(f"""
        CREATE TABLE {table_name} (
            symbol STRING,
            funding_rate_pct DOUBLE,
            oi_delta_pct DOUBLE,
            `timestamp` BIGINT,
            sent_ts AS TO_TIMESTAMP_LTZ(`timestamp`, 3),
            WATERMARK FOR sent_ts AS sent_ts - INTERVAL '10' SECOND
        ) WITH (
            'connector' = 'kafka',
            'topic' = '{TOPIC_SENTIMENT}',
            'properties.bootstrap.servers' = '{KAFKA_BOOTSTRAP}',
            'properties.group.id' = '{KAFKA_GROUP_ID}',
            'format' = 'json',
            'json.ignore-parse-errors' = 'true',
            'scan.startup.mode' = 'latest-offset'
        )
    """)
    return table_name

def create_onchain_source(table_env):
    table_name = "source_onchain"
    table_env.execute_sql(f"""
        CREATE TABLE {table_name} (
            symbol STRING,
            tx_type STRING,
            amount DOUBLE,
            `timestamp` BIGINT,
            chain_ts AS TO_TIMESTAMP_LTZ(`timestamp`, 3),
            WATERMARK FOR chain_ts AS chain_ts - INTERVAL '10' SECOND
        ) WITH (
            'connector' = 'kafka',
            'topic' = '{TOPIC_ONCHAIN}',
            'properties.bootstrap.servers' = '{KAFKA_BOOTSTRAP}',
            'properties.group.id' = '{KAFKA_GROUP_ID}',
            'format' = 'json',
            'json.ignore-parse-errors' = 'true',
            'scan.startup.mode' = 'latest-offset'
        )
    """)
    return table_name

# ==============================================================================
# SINKERS: 4 VÒI XẢ DỮ LIỆU TỪ FLINK RA NGOÀI (KAFKA & ICEBERG LAKEHOUSE)
# ==============================================================================
# Create a Kafka sink to store errors from Flink Logic (for Kafka Connect to BQ)
def create_dlq_sink(table_env):
    table_name = "dlq_flink_logic_errors"
    table_env.execute_sql(f"""
        CREATE TABLE {table_name} (
            source_name STRING,
            raw_payload STRING,
            error_reason STRING,
            event_time TIMESTAMP(3)
        ) WITH (
            'connector' = 'kafka',
            'topic' = 'dlq_flink_logic_errors',
            'properties.bootstrap.servers' = '{KAFKA_BOOTSTRAP}',
            'format' = 'json'
        )
    """)
    return table_name
# Create a Kafka sink to store market alerts (for Kafka Connect to BQ)
def bq_create_alerts_sink(table_env):
    table_name = "bq_alerts_sink"
    table_env.execute_sql(f"""
        CREATE TABLE {table_name} (
            alert_type STRING,
            symbol STRING,
            alert_message STRING,
            event_time TIMESTAMP(3),
            PRIMARY KEY (symbol, event_time, alert_type) NOT ENFORCED
        ) WITH (
            'connector' = 'upsert-kafka',
            'topic' = '{TOPIC_ALERTS_OUTPUT}',
            'properties.bootstrap.servers' = '{KAFKA_BOOTSTRAP}',
            'key.format' = 'json',
            'value.format' = 'json',
            'value.fields-include' = 'ALL'
        )
    """)
    return table_name

def gcs_create_iceberg_sink_raw(table_env):
    """Sink 2: Đẩy Raw Trades xuống GCS làm Data Lake"""
    table_name = "iceberg_catalog.iceberg_db.trades_raw" 
    table_env.execute_sql(f"""
        CREATE TABLE IF NOT EXISTS {table_name} (
            symbol STRING,
            trade_id BIGINT,
            price DOUBLE,
            quantity DOUBLE,
            event_time BIGINT,
            trade_time BIGINT,
            dt STRING,
            hr STRING
        ) 
        PARTITIONED BY (dt, hr)
        WITH (
            'format-version'='2',
            'write.format.default'='parquet',
            'write.parquet.compression-codec'='snappy',
            'write.target-file-size-bytes'='134217728'
        )
    """)
    return table_name

def gcs_create_iceberg_sink_candlestick(table_env):
    """Sink 3: Đẩy Raw Candlesticks xuống GCS dùng APACHE ICEBERG"""
    table_name = "iceberg_catalog.iceberg_db.candlestick_raw"
    table_env.execute_sql(f"""
        CREATE TABLE IF NOT EXISTS {table_name} (
            symbol STRING,
            trade_id BIGINT,
            open_price DOUBLE,
            high_price DOUBLE,
            low_price DOUBLE,
            close_price DOUBLE,
            volume DOUBLE,
            VWAP DOUBLE,
            sma20 DOUBLE,
            upper_band DOUBLE,
            lower_band DOUBLE,
            dt STRING
        ) 
        PARTITIONED BY (dt)
        WITH (
            'format-version'='2',
            'write.format.default'='parquet',
            'write.target-file-size-bytes'='134217728'
        )
    """)
    return table_name

def bq_create_events_sink_candlestick(table_env):
    """Sink 4: Đẩy nến 1 phút + Bollinger Bands vào Kafka (Kafka Connect đẩy lên BQ)"""
    table_name = "bq_candlestick_bb_sink"
    table_env.execute_sql(f"""
        CREATE TABLE {table_name} (
            window_start TIMESTAMP(3),
            window_end TIMESTAMP(3),
            symbol STRING,
            trade_id BIGINT,
            open_price DOUBLE,
            high_price DOUBLE,
            low_price DOUBLE,
            close_price DOUBLE,
            volume DOUBLE,
            VWAP DOUBLE,
            sma20 DOUBLE,
            upper_band DOUBLE,
            lower_band DOUBLE
        ) WITH (
            'connector' = 'kafka',
            'topic' = '{TOPIC_RAW_CANDLESTICK}',
            'properties.bootstrap.servers' = '{KAFKA_BOOTSTRAP}',
            'format' = 'json',
            'sink.delivery-guarantee' = 'at-least-once',
            'properties.enable.idempotence' = 'false',
            'properties.transaction.timeout.ms' = '900000'
        )
    """)
    return table_name