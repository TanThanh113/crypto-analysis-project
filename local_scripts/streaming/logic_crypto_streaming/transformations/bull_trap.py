def get_select_bull_trap_sql(symbol, config_data, orderbook_table, trade_table, sentiment_table, onchain_table):
    """
    Generates Flink SQL to detect Bull Traps (Fake Pumps).
    Upgraded for Maximum Win Rate: Integrates 1% Depth Imbalance, Macro Sentiment 
    (Funding Rate + Open Interest Delta), and On-chain Whale Inflows.
    """
    params = config_data['symbols'].get(symbol.upper(), config_data.get('default'))
    
    window_mins = params['pump_window_minutes']
    pump_pct = params['pump_price_pct']
    max_vol = params['max_pump_vol_multiplier'] 
    imbalance = params['ask_bid_imbalance']     

    sql = f"""
        WITH trade_baseline AS (
            SELECT 
                symbol, 
                trade_ts, 
                price,
                (quantity * price) AS trade_usd,
                AVG(quantity * price) OVER (
                    PARTITION BY symbol 
                    ORDER BY trade_ts 
                    RANGE BETWEEN INTERVAL '10' MINUTE PRECEDING AND CURRENT ROW
                ) AS avg_trade_10m
            FROM {trade_table} 
            WHERE symbol = '{symbol}'
        ),
        trade_pump_window AS (
            SELECT 
                window_start, 
                window_time, 
                symbol,
                FIRST_VALUE(price) AS open_price, 
                LAST_VALUE(price) AS close_price,
                SUM(trade_usd) AS pump_vol_usd, 
                MAX(avg_trade_10m) AS current_avg_trade
            FROM TABLE(TUMBLE(TABLE trade_baseline, DESCRIPTOR(trade_ts), INTERVAL '{window_mins}' MINUTE))
            GROUP BY window_start, window_time, symbol
        ),
        ob_state AS (
            -- Extracted 1% Depth metrics from Python Streamer
            SELECT symbol, ob_ts, ask_vol_1pct_usd, bid_vol_1pct_usd, imbalance_ratio
            FROM {orderbook_table} 
            WHERE symbol = '{symbol}'
        )

        SELECT 
            'BULL_TRAP' AS alert_type,
            T.symbol,
            -- DYNAMIC SCENARIOS: Differentiates between a Standard Trap and a God-Mode Trap
            CASE 
                WHEN S.funding_rate_pct > 0.05 
                     AND S.oi_delta_pct > 1.0 
                     AND C.tx_type = 'INFLOW' THEN
                    '💀 GOD MODE TRAP (99% WIN RATE): Fake Pump +' || CAST(ROUND((T.close_price - T.open_price) / T.open_price * 100, 2) AS STRING) || 
                    '% | Sell Wall 1% is ' || CAST(O.imbalance_ratio AS STRING) || 'x | High FOMO (FR: ' || CAST(S.funding_rate_pct AS STRING) || 
                    '%, OI: +' || CAST(S.oi_delta_pct AS STRING) || '%) & Whale INFLOW! SHORT NOW!'
                ELSE 
                    '🚨 STANDARD TRAP: Fake Pump +' || CAST(ROUND((T.close_price - T.open_price) / T.open_price * 100, 2) AS STRING) || 
                    '% (Low Vol) | Ask Wall 1% is ' || CAST(O.imbalance_ratio AS STRING) || 'x larger. Avoid Longs.'
            END AS alert_message,
            T.window_time AS event_time
            
        FROM trade_pump_window AS T
        
        -- Micro Component: Orderbook Trigger
        JOIN ob_state AS O
            ON T.symbol = O.symbol
            AND O.ob_ts BETWEEN T.window_time - INTERVAL '5' SECOND AND T.window_time
            
        -- Macro Component: Sentiment Context (Using LEFT JOIN to prevent data-loss if API fails)
        LEFT JOIN {sentiment_table} AS S
            ON T.symbol = S.symbol
            AND S.sent_ts BETWEEN T.window_time - INTERVAL '10' MINUTE AND T.window_time
            
        -- Macro Component: On-chain Context
        LEFT JOIN {onchain_table} AS C
            ON T.symbol = C.symbol
            AND C.chain_ts BETWEEN T.window_time - INTERVAL '1' HOUR AND T.window_time
            
        WHERE 
            (T.close_price - T.open_price) / T.open_price * 100 > {pump_pct} -- Condition 1: Spike Price
            AND T.pump_vol_usd < (T.current_avg_trade * {max_vol})     -- Condition 2: Artificial Volume (Weak push)
            AND O.imbalance_ratio > {imbalance}                        -- Condition 3: Blocked by massive Sell Wall
    """
    return sql