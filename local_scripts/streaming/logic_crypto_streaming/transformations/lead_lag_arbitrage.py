def get_select_lead_lag_arbitrage_sql(leader_symbol, lagger_symbol, config_data, trade_table, sentiment_table, onchain_table):
    """
    Generates Flink SQL to detect Latency Arbitrage (Lead-Lag Effect).
    UPGRADED: Enriched with Macro Sentiment and On-chain data.
    If the Leader dumps/pumps and the Lagger is delayed, we verify with Whale flows 
    and Retail FOMO to filter out network noise and generate God-Mode Snipes.
    """
    window_secs = config_data.get('lead_lag_window_seconds', 3)  
    leader_move_pct = config_data.get('leader_move_pct', 0.5)    
    lagger_delay_pct = config_data.get('lagger_delay_pct', 0.1)  

    sql = f"""
        WITH 
        trade_window AS (
            SELECT 
                window_start, window_time, symbol,
                FIRST_VALUE(price) AS open_price,
                LAST_VALUE(price) AS close_price,
                (LAST_VALUE(price) - FIRST_VALUE(price)) / FIRST_VALUE(price) * 100 AS price_change_pct
            FROM TABLE(TUMBLE(TABLE {trade_table}, DESCRIPTOR(trade_ts), INTERVAL '{window_secs}' SECOND))
            WHERE symbol IN ('{leader_symbol}', '{lagger_symbol}')
            GROUP BY window_start, window_time, symbol
        ),
        leader_stats AS (
            SELECT window_start, window_time, price_change_pct AS leader_change
            FROM trade_window WHERE symbol = '{leader_symbol}'
        ),
        lagger_stats AS (
            SELECT window_start, window_time, close_price AS lagger_current_price, price_change_pct AS lagger_change
            FROM trade_window WHERE symbol = '{lagger_symbol}'
        )

        SELECT 
            'LEAD_LAG_ARBITRAGE' AS alert_type,
            '{lagger_symbol}' AS symbol,
            CASE 
                -- GOD MODE BEARISH DELAY
                WHEN L.leader_change <= -{leader_move_pct} AND F.lagger_change > -{lagger_delay_pct} 
                     AND S.funding_rate_pct > 0.05 AND C.tx_type = 'INFLOW' THEN
                    '📉 GOD MODE ARBITRAGE (SHORT): Leader (' || '{leader_symbol}' || ') dumped ' || CAST(ROUND(L.leader_change, 2) AS STRING) || 
                    '% but Lagger (' || '{lagger_symbol}' || ') delayed! Trapped Longs (FR: ' || CAST(S.funding_rate_pct AS STRING) || 
                    '%) + Whale INFLOW! SNIPE SHORT NOW at $' || CAST(ROUND(F.lagger_current_price, 2) AS STRING) || '!'

                -- GOD MODE BULLISH DELAY
                WHEN L.leader_change >= {leader_move_pct} AND F.lagger_change < {lagger_delay_pct} 
                     AND S.funding_rate_pct < 0 AND C.tx_type = 'OUTFLOW' THEN
                    '📈 GOD MODE ARBITRAGE (LONG): Leader (' || '{leader_symbol}' || ') pumped +' || CAST(ROUND(L.leader_change, 2) AS STRING) || 
                    '% but Lagger (' || '{lagger_symbol}' || ') delayed! Trapped Shorts (FR: ' || CAST(S.funding_rate_pct AS STRING) || 
                    '%) + Whale OUTFLOW! SNIPE LONG NOW at $' || CAST(ROUND(F.lagger_current_price, 2) AS STRING) || '!'

                -- STANDARD SCENARIOS
                WHEN L.leader_change <= -{leader_move_pct} AND F.lagger_change > -{lagger_delay_pct} THEN
                    '🚨 STANDARD ARBITRAGE: Leader dumped, Lagger delayed. Potential Short on ' || '{lagger_symbol}'
                ELSE
                    '🚨 STANDARD ARBITRAGE: Leader pumped, Lagger delayed. Potential Long on ' || '{lagger_symbol}'
            END AS alert_message,
            L.window_time AS event_time

        FROM leader_stats L
        JOIN lagger_stats F 
            ON L.window_time = F.window_time 
            AND L.window_start = F.window_start
        
        LEFT JOIN {sentiment_table} AS S 
            ON S.symbol = '{lagger_symbol}' 
            AND S.sent_ts BETWEEN L.window_time - INTERVAL '10' MINUTE AND L.window_time
            
        LEFT JOIN {onchain_table} AS C 
            ON C.symbol = '{lagger_symbol}' 
            AND C.chain_ts BETWEEN L.window_time - INTERVAL '1' HOUR AND L.window_time
        
        WHERE 
            (L.leader_change <= -{leader_move_pct} AND F.lagger_change > -{lagger_delay_pct})
            OR 
            (L.leader_change >= {leader_move_pct} AND F.lagger_change < {lagger_delay_pct})
    """
    return sql