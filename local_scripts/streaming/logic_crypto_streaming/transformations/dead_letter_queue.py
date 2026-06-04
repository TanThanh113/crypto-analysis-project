def collected_junk_from_trade_sources(statement_set, source_trades, sink_dlq):
    statement_set.add_insert_sql(f"""
        INSERT INTO {sink_dlq}
        SELECT 
            'crypto_trades' AS source_name,
            JSON_OBJECT(
                KEY 'symbol' VALUE symbol,
                KEY 'price' VALUE price,
                KEY 'quantity' VALUE quantity,
                KEY 'trade_time' VALUE trade_time
            ) AS raw_payload,
            'Error: price <= 0, quantity <= 0, or symbol is null' AS error_reason,
            CURRENT_TIMESTAMP
        FROM {source_trades}
        WHERE price <= 0 OR quantity <= 0 OR symbol IS NULL
    """)

def collected_junk_from_orderbook_sources(statement_set, source_orderbook, sink_dlq):
    statement_set.add_insert_sql(f"""
        INSERT INTO {sink_dlq}
        SELECT 
            'crypto_orderbook' AS source_name,
            JSON_OBJECT(
                KEY 'symbol' VALUE symbol,
                KEY 'best_bid_price' VALUE best_bid_price,
                KEY 'best_ask_price' VALUE best_ask_price,
                KEY 'best_bid_qty' VALUE best_bid_qty,
                KEY 'best_ask_qty' VALUE best_ask_qty,
                KEY 'bid_vol_1pct_usd' VALUE bid_vol_1pct_usd,
                KEY 'ask_vol_1pct_usd' VALUE ask_vol_1pct_usd,
                KEY 'ob_ts' VALUE ob_ts
            ) AS raw_payload,
            'Error: invalid prices (<=0), negative quantities, or symbol null' AS error_reason,
            CURRENT_TIMESTAMP
        FROM {source_orderbook}
        WHERE best_bid_price <= 0 
           OR best_ask_price <= 0 
           OR best_bid_qty < 0 
           OR best_ask_qty < 0 
           OR symbol IS NULL
    """)

def collected_junk_from_liquidations_sources(statement_set, source_liquidations, sink_dlq):
    statement_set.add_insert_sql(f"""
        INSERT INTO {sink_dlq}
        SELECT 
            'crypto_liquidations' AS source_name,
            JSON_OBJECT(
                KEY 'symbol' VALUE symbol,
                KEY 'side' VALUE side,
                KEY 'price' VALUE price,
                KEY 'quantity' VALUE quantity,
                KEY 'liq_ts' VALUE liq_ts
            ) AS raw_payload,
            'Error: price <= 0, quantity <= 0, or symbol is null' AS error_reason,
            CURRENT_TIMESTAMP
        FROM {source_liquidations}
        WHERE price <= 0 OR quantity <= 0 OR symbol IS NULL
    """)

def collected_junk_from_sentiment_sources(statement_set, source_sentiment, sink_dlq):
    statement_set.add_insert_sql(f"""
        INSERT INTO {sink_dlq}
        SELECT 
            'crypto_sentiment' AS source_name,
            JSON_OBJECT(
                KEY 'symbol' VALUE symbol,
                KEY 'funding_rate_pct' VALUE funding_rate_pct,
                KEY 'oi_delta_pct' VALUE oi_delta_pct,
                KEY 'sent_ts' VALUE sent_ts
            ) AS raw_payload,
            'Error: Missing vital data (symbol, funding_rate, or oi_delta is null)' AS error_reason,
            CURRENT_TIMESTAMP
        FROM {source_sentiment}
        WHERE symbol IS NULL 
           OR funding_rate_pct IS NULL 
           OR oi_delta_pct IS NULL
    """)

def collected_junk_from_onchain_sources(statement_set, source_onchain, sink_dlq):
    statement_set.add_insert_sql(f"""
        INSERT INTO {sink_dlq}
        SELECT 
            'crypto_onchain_alerts' AS source_name,
            JSON_OBJECT(
                KEY 'symbol' VALUE symbol,
                KEY 'tx_type' VALUE tx_type,
                KEY 'amount' VALUE amount,
                KEY 'chain_ts' VALUE chain_ts
            ) AS raw_payload,
            'Error: amount <= 0 or symbol is null' AS error_reason,
            CURRENT_TIMESTAMP
        FROM {source_onchain}
        WHERE amount <= 0 OR symbol IS NULL
    """)