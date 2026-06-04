# -*- coding: utf-8 -*-

import os
import logging
import datetime
from pyflink.datastream import StreamExecutionEnvironment
from pyflink.table import StreamTableEnvironment, EnvironmentSettings

from config import BUCKET_NAME
from utils.config_parser import load_config

import connectors

from transformations.bull_trap import get_select_bull_trap_sql
from transformations.true_breakout import get_select_true_breakout_sql
from transformations.bottom_catcher import get_select_bottom_catcher_sql
from transformations.spoofing_detection import get_select_spoofing_alert_sql
from transformations.liquidation_cascade import get_select_liquidation_cascade_sql
from transformations.lead_lag_arbitrage import get_select_lead_lag_arbitrage_sql
from transformations.micro_mean_reversion import get_select_micro_mean_reversion_sql
from transformations.order_flow_imbalance import get_select_ofi_hidden_orders_sql

from transformations.core_etl import (
    create_view_candlesticks,
    get_insert_raw_data_sql,
    get_insert_raw_candlestick,
    get_insert_candlestick_bb_sql
)

from transformations.dead_letter_queue import (
    collected_junk_from_trade_sources,
    collected_junk_from_orderbook_sources,
    collected_junk_from_liquidations_sources,
    collected_junk_from_sentiment_sources,
    collected_junk_from_onchain_sources
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
def run_crypto_pipeline():
    
    logging.info("📊 Initializing Flink Quant Trading Pipeline...")
    
    # -------------------------------------------------------------
    # Create a custom Flink environment
    # -------------------------------------------------------------
    env = StreamExecutionEnvironment.get_execution_environment()
    settings = EnvironmentSettings.new_instance().in_streaming_mode().build()
    table_env = StreamTableEnvironment.create(env, environment_settings=settings)

    conf = table_env.get_config()
    conf.set("table.exec.source.idle-timeout", "10 s")
    conf.set_idle_state_retention(datetime.timedelta(minutes=15))

    # -------------------------------------------------------------
    #  Enable mini-batching
    # -------------------------------------------------------------
    conf.set("table.exec.mini-batch.enabled", "true")
    conf.set("table.exec.mini-batch.allow-latency", "1 s")
    conf.set("table.exec.mini-batch.size", "1000")

    env.disable_operator_chaining()

    # -------------------------------------------------------------
    # Enable checkpointing and save checkpoints to GCS
    # -------------------------------------------------------------
    env.enable_checkpointing(60000)

    checkpoint_config = env.get_checkpoint_config()
    checkpoint_config.set_min_pause_between_checkpoints(10000)
    checkpoint_config.set_checkpoint_timeout(600000)
    
    checkpoint_config.set_max_concurrent_checkpoints(1)
    checkpoint_config.set_tolerable_checkpoint_failure_number(3)

    # Save checkpoints to GCS
    checkpoint_config.set_checkpoint_storage_dir(f"gs://{BUCKET_NAME}/flink_checkpoints/")
    logging.info("✅ Flink Environment and Checkpoints initialized successfully.")

    # -------------------------------------------------------------
    # Load JAR files from GCS
    # -------------------------------------------------------------
    jar_dir = "/tmp/flink_jars"
    if os.path.exists(jar_dir):
        jar_files = [f"file://{os.path.join(jar_dir, j)}" for j in os.listdir(jar_dir) if j.endswith(".jar")]
        if jar_files:
            table_env.get_config().get_configuration().set_string("pipeline.jars", ";".join(jar_files))
            logging.info(f"🚀 Completed loading JAR files: {jar_files}")

    # -------------------------------------------------------------
    # COMPILE STATEMENT SET FOR QUANT LOGIC & ETL   
    # -------------------------------------------------------------
    # Compile Statement Set for Quant Logic & ETL
    logging.info("🚀 Compiling Statement Set for Quant Logic & ETL...")
    statement_set = table_env.create_statement_set()
    symbols_to_track = ["BTCUSDT", "ETHUSDT"]

    # -------------------------------------------------------------
    # LOAD CONFIG FILE & CREATE ICEBERG CATALOG
    # -------------------------------------------------------------
    config_data = load_config("configs/trading_params.yaml")
    connectors.setup_iceberg_catalog(table_env)

    # -------------------------------------------------------------
    # CREATE KAFKA SOURCE & SINK CONNECTORS
    # -------------------------------------------------------------
    # Initialize 5 Input Tables
    logging.info("🚀 Registering Source Connectors...")
    source_trades = connectors.create_trade_source(table_env)
    source_ob = connectors.create_orderbook_source(table_env)
    source_liq = connectors.create_liquidation_source(table_env)
    source_sent = connectors.create_sentiment_source(table_env)
    source_onchain = connectors.create_onchain_source(table_env)

    # Initialize 5 Output Tables
    logging.info("🚀 Registering Sink Connectors...")
    sink_alerts = connectors.bq_create_alerts_sink(table_env)
    sink_bq_candles = connectors.bq_create_events_sink_candlestick(table_env)

    # Initialize 2 Output Iceberg Tables
    sink_iceberg_trades = connectors.gcs_create_iceberg_sink_raw(table_env)
    sink_iceberg_candles = connectors.gcs_create_iceberg_sink_candlestick(table_env)

    # Initialize 1 Output Table for Flink Logic Errors(Dead Letter Queue)
    sink_dlq = connectors.create_dlq_sink(table_env)

    logging.info("✅ Registered all Connectors (DDL).")

    # -------------------------------------------------------------
    # Collect trash from all sources.
    # -------------------------------------------------------------
    # 1. Trades with price and quantity <= 0
    collected_junk_from_trade_sources(statement_set, source_trades=source_trades, sink_dlq=sink_dlq)
    # 2. Orderbook with best_bid_price, best_ask_price <= 0, best_bid_qty < 0, best_ask_qty < 0
    collected_junk_from_orderbook_sources(statement_set, source_orderbook=source_ob, sink_dlq=sink_dlq)
    # 3. Liquidations with price and quantity <= 0
    collected_junk_from_liquidations_sources(statement_set, source_liquidations=source_liq, sink_dlq=sink_dlq)
    # 4. Sentiment with funding_rate_pct and oi_delta_pct <= 0
    collected_junk_from_sentiment_sources(statement_set, source_sentiment=source_sent, sink_dlq=sink_dlq)
    # 5. Onchain with amount <= 0
    collected_junk_from_onchain_sources(statement_set, source_onchain=source_onchain, sink_dlq=sink_dlq)

    # -------------------------------------------------------------
    # ETL & Candlestick Calculation (Using a Clean View)
    # -------------------------------------------------------------
    # Create a view to calculate candlestick data
    logging.info("🚀 Creating Temporary Views...")
    create_view_candlesticks(table_env, source_trades)
    logging.info("✅ Created Temporary Views.")

    # Insert Candlestick Bollinger Bands and Vwap to BigQuery
    statement_set.add_insert_sql(get_insert_candlestick_bb_sql(sink_bq_candles))

    # Insert 2 file (Raw Trades and candlesticks) to Iceberg
    statement_set.add_insert_sql(get_insert_raw_data_sql(source_trades, sink_iceberg_trades))
    statement_set.add_insert_sql(get_insert_raw_candlestick(sink_iceberg_candles))

    # -------------------------------------------------------------
    # RUNNING QUANT LOGIC TO CATCH SHARKS (USING 100% CLEAN DATA)
    # -------------------------------------------------------------
    
    # Logic for all symbols
    for sym in symbols_to_track:
        # Bull Trap
        statement_set.add_insert_sql(f"INSERT INTO {sink_alerts} " + 
            get_select_bull_trap_sql(
                symbol=sym, config_data=config_data, 
                trade_table=source_trades, orderbook_table=source_ob,
                sentiment_table=source_sent, onchain_table=source_onchain
            )
        )
        
        # True Breakout
        statement_set.add_insert_sql(f"INSERT INTO {sink_alerts} " + 
            get_select_true_breakout_sql(
                symbol=sym, config_data=config_data, 
                trade_table=source_trades, orderbook_table=source_ob, 
                sentiment_table=source_sent, onchain_table=source_onchain
            )
        )
        
        # Bottom Catcher
        statement_set.add_insert_sql(f"INSERT INTO {sink_alerts} " + 
            get_select_bottom_catcher_sql(
                symbol=sym, config_data=config_data, 
                liquidation_table=source_liq, trade_table=source_trades, 
                orderbook_table=source_ob, sentiment_table=source_sent, 
                onchain_table=source_onchain
            )
        )
        
        # Spoofing
        statement_set.add_insert_sql(f"INSERT INTO {sink_alerts} " + 
            get_select_spoofing_alert_sql(
                symbol=sym, config_data=config_data, 
                trade_table=source_trades, orderbook_table=source_ob,
                sentiment_table=source_sent, onchain_table=source_onchain
            )
        )
        # Micro Mean Reversion
        statement_set.add_insert_sql(f"INSERT INTO {sink_alerts} " + 
            get_select_micro_mean_reversion_sql(
                symbol=sym, config_data=config_data, 
                trade_table=source_trades, orderbook_table=source_ob
            )
        )
        # Order Flow Imbalance
        statement_set.add_insert_sql(f"INSERT INTO {sink_alerts} " + 
            get_select_ofi_hidden_orders_sql(
                symbol=sym, config_data=config_data, 
                orderbook_table=source_ob, sentiment_table=source_sent, 
                onchain_table=source_onchain
            )
        )
        # Liquidation Cascade
        statement_set.add_insert_sql(f"INSERT INTO {sink_alerts} " + 
            get_select_liquidation_cascade_sql(
                symbol=sym, config_data=config_data,
                liquidation_table=source_liq, orderbook_table=source_ob,
                sentiment_table=source_sent, onchain_table=source_onchain
            )
        )

    # Lead Lag Arbitrage
    statement_set.add_insert_sql(f"INSERT INTO {sink_alerts} " + 
        get_select_lead_lag_arbitrage_sql(
            leader_symbol="BTCUSDT", lagger_symbol="ETHUSDT", config_data=config_data, 
            trade_table=source_trades, sentiment_table=source_sent, onchain_table=source_onchain
        )
    )

    # -------------------------------------------------------------
    # EXECUTE PIPELINE
    # -------------------------------------------------------------
    logging.info("✅ Statement Set Compiled. Starting execution...")
    logging.info("🔥 EXECUTING PIPELINE TO DATAPROC CLUSTER 🔥")
    statement_set.execute().wait()

if __name__ == "__main__":
    # Run the crypto pipeline
    run_crypto_pipeline()