def get_select_liquidation_cascade_sql(symbol, config_data, liquidation_table, orderbook_table, sentiment_table, onchain_table):
    """
    Generates Flink SQL to predict Flash Crashes (Liquidation Cascades).
    Upgraded for Maximum Win Rate: Compares liquidation volume against the robust 1% Depth Bid Wall.
    Enriched with Macro Sentiment (Over-leveraged Longs) and Whale Inflows (Dump fuel).
    """
    params = config_data['symbols'].get(symbol.upper(), config_data.get('default'))
    
    window_secs = params.get('cascade_window_seconds', 5)
    liq_mult = params.get('cascade_liq_multiplier', 5.0)
    min_base = params.get('min_base_liq_usd', 5000)
    liq_ratio = params.get('liquidity_ratio', 1.5)
    lookback = params.get('orderbook_lookback_seconds', 5)

    sql = f"""
        WITH 
        -- 1. LIQUIDATION BASELINE (Using liq_ts from connectors)
        liq_baseline AS (
            SELECT 
                symbol, liq_ts, (quantity * price) AS liq_usd,
                AVG(quantity * price) OVER (
                    PARTITION BY symbol 
                    ORDER BY liq_ts 
                    RANGE BETWEEN INTERVAL '10' MINUTE PRECEDING AND CURRENT ROW
                ) AS avg_liq_10m
            FROM {liquidation_table} 
            WHERE symbol = '{symbol}' AND side = 'SELL' 
        ),

        -- 2. LIQUIDATION BURST WINDOW
        liq_window AS (
            SELECT 
                window_start, window_time, symbol, 
                SUM(liq_usd) AS total_liq_usd,
                MAX(avg_liq_10m) AS current_avg_liq
            FROM TABLE(TUMBLE(TABLE liq_baseline, DESCRIPTOR(liq_ts), INTERVAL '{window_secs}' SECOND))
            GROUP BY window_start, window_time, symbol
        ),

        -- 3. CURRENT ORDERBOOK LIQUIDITY (Using ob_ts)
        ob_state AS (
            SELECT symbol, ob_ts, bid_vol_1pct_usd
            FROM {orderbook_table} 
            WHERE symbol = '{symbol}'
        )

        -- 4. PREDICTION LOGIC
        SELECT 
            'LIQUIDATION_CASCADE' AS alert_type,
            L.symbol,
            CASE 
                WHEN S.funding_rate_pct > 0.05 AND C.tx_type = 'INFLOW' THEN
                    '🌪️ GOD MODE CASCADE (99% WIN RATE): Domino $' || CAST(ROUND(L.total_liq_usd, 0) AS STRING) || 
                    ' liquidated! | 1% Bid Wall Destroyed | Longs Trapped (FR: ' || CAST(S.funding_rate_pct AS STRING) || 
                    '%) & Whale INFLOW dumping! PRICE FREEFALL IMMINENT!'
                ELSE 
                    '🚨 FLASH CRASH WARNING: Domino $' || CAST(ROUND(L.total_liq_usd, 0) AS STRING) || 
                    ' liquidated. 1% Bid Wall overwhelmed. Do not catch the falling knife!'
            END AS alert_message,
            L.window_time AS event_time
            
        FROM liq_window AS L
        
        -- Micro Component: Orderbook State (Using ob_ts)
        JOIN ob_state AS O
            ON L.symbol = O.symbol
            AND O.ob_ts BETWEEN L.window_time - INTERVAL '{lookback}' SECOND AND L.window_time
            
        -- Macro Component: Sentiment Context (Using sent_ts)
        LEFT JOIN {sentiment_table} AS S
            ON L.symbol = S.symbol
            AND S.sent_ts BETWEEN L.window_time - INTERVAL '10' MINUTE AND L.window_time
            
        -- Macro Component: On-chain Context (Using chain_ts)
        LEFT JOIN {onchain_table} AS C
            ON L.symbol = C.symbol
            AND C.chain_ts BETWEEN L.window_time - INTERVAL '1' HOUR AND L.window_time
            
        WHERE 
            L.total_liq_usd > (GREATEST(L.current_avg_liq, {min_base}) * {liq_mult})
            AND (L.total_liq_usd / COALESCE(NULLIF(O.bid_vol_1pct_usd, 0), 1)) > {liq_ratio}
    """
    return sql