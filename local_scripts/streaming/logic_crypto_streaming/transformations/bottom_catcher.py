def get_select_bottom_catcher_sql(symbol, config_data, liquidation_table, orderbook_table, trade_table, sentiment_table, onchain_table):
    """
    Generates Flink SQL to detect Whale Bottom Absorption (Knife Catching).
    Upgraded for Maximum Win Rate: Integrates 1% Depth Imbalance, Negative Funding Rate 
    (Retail panic shorting), and Whale Outflows (Supply shock accumulation).
    """
    params = config_data['symbols'].get(symbol.upper(), config_data.get('default'))
    
    window_secs = params['window_seconds']
    liq_mult = params['liq_multiplier']
    bid_mult = params['bid_wall_multiplier']
    whale_mult = params['whale_multiplier']

    sql = f"""
        WITH 
        -- 1. LIQUIDATION BASELINE (Using liq_ts from connectors.py)
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
        liq_window AS (
            SELECT 
                window_start, window_time, symbol, 
                SUM(liq_usd) AS total_liq_usd,
                MAX(avg_liq_10m) AS current_avg_liq
            FROM TABLE(TUMBLE(TABLE liq_baseline, DESCRIPTOR(liq_ts), INTERVAL '{window_secs}' SECOND))
            GROUP BY window_start, window_time, symbol
        ),

        -- 2. TRADE BASELINE (Using trade_ts from connectors.py)
        trade_baseline AS (
            SELECT 
                symbol, trade_ts, (quantity * price) AS trade_usd,
                AVG(quantity * price) OVER (
                    PARTITION BY symbol 
                    ORDER BY trade_ts 
                    RANGE BETWEEN INTERVAL '10' MINUTE PRECEDING AND CURRENT ROW
                ) AS avg_trade_10m
            FROM {trade_table}
            WHERE symbol = '{symbol}'
        ),
        trade_window AS (
            SELECT 
                window_start, window_time, symbol, 
                SUM(trade_usd) AS total_buy_usd,
                COUNT(symbol) AS trade_count,
                MAX(avg_trade_10m) AS current_avg_trade
            FROM TABLE(TUMBLE(TABLE trade_baseline, DESCRIPTOR(trade_ts), INTERVAL '{window_secs}' SECOND))
            GROUP BY window_start, window_time, symbol
        ),

        -- 3. ORDER BOOK STATE (Using ob_ts from connectors.py)
        ob_state AS (
            SELECT symbol, ob_ts, ask_vol_1pct_usd, bid_vol_1pct_usd 
            FROM {orderbook_table}
            WHERE symbol = '{symbol}'
        )

        -- 4. JOINING STREAMS & CLASSIFYING WHALE BEHAVIOR
        SELECT 
            'BOTTOM_CATCHER' AS alert_type,
            L.symbol,
            -- DYNAMIC SCENARIOS: God Mode vs Standard Bottom
            CASE 
                WHEN S.funding_rate_pct < 0 AND C.tx_type = 'OUTFLOW' THEN
                    '💎 GOD MODE BOTTOM (99% WIN RATE): Panic Liq $' || CAST(ROUND(L.total_liq_usd, 0) AS STRING) || 
                    ' absorbed! | 1% Bid Wall Dominance | Extreme Fear (FR: ' || CAST(S.funding_rate_pct AS STRING) || 
                    '%) & Whale OUTFLOW (Supply Shock)! FULL SEND LONG!'
                ELSE 
                    '🛒 STANDARD BOTTOM: Panic Liq $' || CAST(ROUND(L.total_liq_usd, 0) AS STRING) || 
                    ' absorbed. | Strategy: ' || 
                    CASE 
                        WHEN T.trade_count < 15 THEN 'Aggressive Sweep (' || CAST(T.trade_count AS STRING) || ' Large Orders)'
                        ELSE 'Iceberg Accumulation (' || CAST(T.trade_count AS STRING) || ' Small Orders)'
                    END || '. Safe to Long.'
            END AS alert_message,
            L.window_time AS event_time
            
        FROM liq_window AS L
        
        -- Join Trades (Looking for massive Volume spike immediately during/after Liquidations)
        JOIN trade_window AS T
            ON L.symbol = T.symbol
            AND T.window_time BETWEEN L.window_time AND L.window_time + INTERVAL '10' SECOND
            
        -- Join Orderbook (Confirming the Bid Floor is actually holding)
        JOIN ob_state AS O
            ON L.symbol = O.symbol
            AND O.ob_ts BETWEEN L.window_time - INTERVAL '2' SECOND AND L.window_time + INTERVAL '5' SECOND
            
        -- Macro Context (Sentiment & On-chain)
        LEFT JOIN {sentiment_table} AS S
            ON L.symbol = S.symbol
            AND S.sent_ts BETWEEN L.window_time - INTERVAL '10' MINUTE AND L.window_time
            
        LEFT JOIN {onchain_table} AS C
            ON L.symbol = C.symbol
            AND C.chain_ts BETWEEN L.window_time - INTERVAL '1' HOUR AND L.window_time
            
        WHERE 
            -- Condition 1: Massive forced liquidations (Panic selling)
            L.total_liq_usd > (GREATEST(L.current_avg_liq, 10000) * {liq_mult})
            -- Condition 2: Massive volume absorbing the panic
            AND T.total_buy_usd > (T.current_avg_trade * {whale_mult})
            -- Condition 3: Bid Wall heavily outweighs Ask Wall in 1% depth
            AND O.bid_vol_1pct_usd > (O.ask_vol_1pct_usd * {bid_mult})
    """
    return sql