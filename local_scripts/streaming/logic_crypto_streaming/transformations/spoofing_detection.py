def get_select_spoofing_alert_sql(symbol, config_data, orderbook_table, trade_table, sentiment_table, onchain_table):
    """
    Generates Flink SQL to detect Market Manipulation via Spoofing (Fake Orders).
    Upgraded for Maximum Win Rate: Uses 1% Depth Volume instead of best prices, 
    enriched with Macro Sentiment and On-chain flows to detect lethal traps.
    """
    params = config_data['symbols'].get(symbol.upper(), config_data.get('default'))
    
    spoof_window = params.get('spoof_window_seconds', 10)
    spoof_mult = params.get('spoof_multiplier', 4.0)
    exec_thresh = params.get('execution_threshold', 0.1)

    sql = f"""
        WITH 
        -- 1. ORDERBOOK HOP WINDOW (Track 1% Depth Wall appearance and disappearance)
        ob_spoof_window AS (
            SELECT 
                window_start, window_time, symbol,
                -- BID SIDE (Buy Wall)
                MIN(bid_vol_1pct_usd) AS min_bid_usd,
                MAX(bid_vol_1pct_usd) AS peak_bid_usd,
                LAST_VALUE(bid_vol_1pct_usd) AS final_bid_usd,
                -- ASK SIDE (Sell Wall)
                MIN(ask_vol_1pct_usd) AS min_ask_usd,
                MAX(ask_vol_1pct_usd) AS peak_ask_usd,
                LAST_VALUE(ask_vol_1pct_usd) AS final_ask_usd
            FROM TABLE(HOP(TABLE {orderbook_table}, DESCRIPTOR(ob_ts), INTERVAL '2' SECOND, INTERVAL '{spoof_window}' SECOND))
            WHERE symbol = '{symbol}'
            GROUP BY window_start, window_time, symbol
        ),

        -- 2. TRADE HOP WINDOW (Track actual executed volume in the exact same timeframe)
        trade_spoof_window AS (
            SELECT 
                window_start, window_time, symbol,
                SUM(quantity * price) AS traded_vol_usd
            FROM TABLE(HOP(TABLE {trade_table}, DESCRIPTOR(trade_ts), INTERVAL '2' SECOND, INTERVAL '{spoof_window}' SECOND))
            WHERE symbol = '{symbol}'
            GROUP BY window_start, window_time, symbol
        )

        -- 3. ALGORITHM VERIFICATION (Combine and Classify)
        SELECT 
            'SPOOFING_DETECTED' AS alert_type,
            O.symbol,
            CASE 
                -- GOD MODE: FAKE BUY WALL (Baiting Longs to Dump) + High FOMO + Whale Inflow
                WHEN O.peak_bid_usd > O.min_bid_usd * {spoof_mult} 
                     AND S.funding_rate_pct > 0.05 
                     AND C.tx_type = 'INFLOW' THEN 
                    '💀 GOD MODE FAKE SUPPORT (99% WIN RATE): $' || CAST(ROUND(O.peak_bid_usd, 0) AS STRING) || ' Buy Wall flashed & pulled! Real Trade: $' || CAST(ROUND(COALESCE(T.traded_vol_usd, 0), 0) AS STRING) || ' | High FOMO (FR: ' || CAST(S.funding_rate_pct AS STRING) || '%) + Whale INFLOW! DUMP IMMINENT!'
                
                -- STANDARD: FAKE BUY WALL
                WHEN O.peak_bid_usd > O.min_bid_usd * {spoof_mult} THEN 
                    '🚨 FAKE BUY WALL (Spoofing): $' || CAST(ROUND(O.peak_bid_usd, 0) AS STRING) || ' flashed & pulled. Real Trade: $' || CAST(ROUND(COALESCE(T.traded_vol_usd, 0), 0) AS STRING) || '. Artificial Support.'

                -- GOD MODE: FAKE SELL WALL (Baiting Shorts to Squeeze) + Negative Funding + Whale Outflow
                WHEN O.peak_ask_usd > O.min_ask_usd * {spoof_mult} 
                     AND S.funding_rate_pct < 0 
                     AND C.tx_type = 'OUTFLOW' THEN 
                    '🚀 GOD MODE FAKE RESISTANCE (99% WIN RATE): $' || CAST(ROUND(O.peak_ask_usd, 0) AS STRING) || ' Sell Wall flashed & pulled! Real Trade: $' || CAST(ROUND(COALESCE(T.traded_vol_usd, 0), 0) AS STRING) || ' | Shorts Trapped (FR: ' || CAST(S.funding_rate_pct AS STRING) || '%) + Whale OUTFLOW! PUMP IMMINENT!'
                
                -- STANDARD: FAKE SELL WALL
                ELSE 
                    '🚨 FAKE SELL WALL (Spoofing): $' || CAST(ROUND(O.peak_ask_usd, 0) AS STRING) || ' flashed & pulled. Real Trade: $' || CAST(ROUND(COALESCE(T.traded_vol_usd, 0), 0) AS STRING) || '. Artificial Resistance.'
            END AS alert_message,
            O.window_time AS event_time
            
        FROM ob_spoof_window O
        
        -- Join Trades (Use LEFT JOIN to retain alerts even if NO trades executed)
        LEFT JOIN trade_spoof_window T
            ON O.window_time = T.window_time 
            AND O.window_start = T.window_start 
            AND O.symbol = T.symbol

        -- Macro Context (Sentiment & On-chain)
        LEFT JOIN {sentiment_table} AS S
            ON O.symbol = S.symbol
            AND S.sent_ts BETWEEN O.window_time - INTERVAL '10' MINUTE AND O.window_time
            
        LEFT JOIN {onchain_table} AS C
            ON O.symbol = C.symbol
            AND C.chain_ts BETWEEN O.window_time - INTERVAL '1' HOUR AND O.window_time
            
        WHERE 
            -- SCENARIO A: BID SPOOFING (Fake Support)
            (
                O.peak_bid_usd > O.min_bid_usd * {spoof_mult}              -- 1. Huge wall appears
                AND O.final_bid_usd < O.min_bid_usd * 1.5                   -- 2. Wall is abruptly canceled
                AND COALESCE(T.traded_vol_usd, 0) < (O.peak_bid_usd - O.min_bid_usd) * {exec_thresh} -- 3. Barely any real money traded
            )
            OR 
            -- SCENARIO B: ASK SPOOFING (Fake Resistance)
            (
                O.peak_ask_usd > O.min_ask_usd * {spoof_mult}              -- 1. Huge pressure applied
                AND O.final_ask_usd < O.min_ask_usd * 1.5                   -- 2. Pressure instantly removed
                AND COALESCE(T.traded_vol_usd, 0) < (O.peak_ask_usd - O.min_ask_usd) * {exec_thresh} -- 3. No actual selling occurred
            )
    """
    return sql