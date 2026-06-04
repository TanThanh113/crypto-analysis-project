def get_select_micro_mean_reversion_sql(symbol, config_data, trade_table, orderbook_table):
    """
    Generates Flink SQL to detect Micro Mean-Reversion opportunities.
    UPGRADED: Combines VWAP Deviation with 1% Depth Orderbook Imbalance.
    Trades are only triggered when price deviates into a massive opposing wall (Bounce effect).
    """
    params = config_data['symbols'].get(symbol.upper(), config_data.get('default'))
    
    window_secs = params.get('scalp_window_seconds', 15)  
    max_vol_mult = params.get('max_chop_vol', 0.5)        
    dev_pct = params.get('vwap_deviation_pct', 0.15)      
    wall_mult = params.get('reversion_wall_multiplier', 2.0) # Tường cản phải dày gấp 2 lần tường đẩy

    sql = f"""
        WITH trade_baseline AS (
            SELECT 
                symbol, trade_ts, price, quantity, (quantity * price) AS trade_usd,
                AVG(quantity * price) OVER (
                    PARTITION BY symbol 
                    ORDER BY trade_ts 
                    RANGE BETWEEN INTERVAL '30' MINUTE PRECEDING AND CURRENT ROW
                ) AS avg_trade_30m
            FROM {trade_table} 
            WHERE symbol = '{symbol}'
        ),
        
        micro_window AS (
            SELECT 
                window_start, window_time, symbol,
                LAST_VALUE(price) AS current_price,
                SUM(trade_usd) AS current_vol_usd,
                MAX(avg_trade_30m) AS baseline_vol_usd,
                -- Tính toán VWAP
                SUM(price * quantity) / SUM(quantity) AS current_vwap
            FROM TABLE(TUMBLE(TABLE trade_baseline, DESCRIPTOR(trade_ts), INTERVAL '{window_secs}' SECOND))
            GROUP BY window_start, window_time, symbol
        ),

        ob_state AS (
            -- Bốc dữ liệu Sổ lệnh 1% để tìm Trần/Sàn nhà
            SELECT symbol, ob_ts, ask_vol_1pct_usd, bid_vol_1pct_usd 
            FROM {orderbook_table} 
            WHERE symbol = '{symbol}'
        )

        SELECT 
            'MICRO_MEAN_REVERSION' AS alert_type,
            T.symbol,
            CASE 
                -- ĐÁNH SHORT: Giá chệch lên trên VWAP VÀ đụng phải Tường Bán (Trần nhà)
                WHEN (T.current_price - T.current_vwap) / T.current_vwap * 100 >= {dev_pct} 
                     AND O.ask_vol_1pct_usd > O.bid_vol_1pct_usd * {wall_mult} THEN
                    '📉 CHOPPY SCALP (SHORT): Price spiked +' || CAST(ROUND((T.current_price - T.current_vwap) / T.current_vwap * 100, 3) AS STRING) || 
                    '% above VWAP but hit a ' || CAST({wall_mult} AS STRING) || 'x Ask Wall! Bounce down expected. SHORT!'
                
                -- ĐÁNH LONG: Giá chệch xuống dưới VWAP VÀ đụng phải Tường Mua (Sàn nhà)
                WHEN (T.current_vwap - T.current_price) / T.current_vwap * 100 >= {dev_pct} 
                     AND O.bid_vol_1pct_usd > O.ask_vol_1pct_usd * {wall_mult} THEN
                    '📈 CHOPPY SCALP (LONG): Price dipped -' || CAST(ROUND((T.current_vwap - T.current_price) / T.current_vwap * 100, 3) AS STRING) || 
                    '% below VWAP but hit a ' || CAST({wall_mult} AS STRING) || 'x Bid Wall! Bounce up expected. LONG!'
            END AS alert_message,
            T.window_time AS event_time
            
        FROM micro_window AS T
        
        -- Kẹp Sổ lệnh vào ngay tại thời điểm cửa sổ VWAP kết thúc
        JOIN ob_state AS O
            ON T.symbol = O.symbol
            AND O.ob_ts BETWEEN T.window_time - INTERVAL '2' SECOND AND T.window_time
            
        WHERE 
            -- ĐIỀU KIỆN 1: Phải là thị trường Sideway (Volume thấp)
            T.current_vol_usd < (T.baseline_vol_usd * {max_vol_mult})
            AND 
            (
                -- ĐIỀU KIỆN 2: Lệch lên trên VWAP + Có Tường Bán chặn lại
                (
                    (T.current_price - T.current_vwap) / T.current_vwap * 100 >= {dev_pct}
                    AND O.ask_vol_1pct_usd > O.bid_vol_1pct_usd * {wall_mult}
                )
                OR 
                -- ĐIỀU KIỆN 3: Lệch xuống dưới VWAP + Có Tường Mua đỡ lại
                (
                    (T.current_vwap - T.current_price) / T.current_vwap * 100 >= {dev_pct}
                    AND O.bid_vol_1pct_usd > O.ask_vol_1pct_usd * {wall_mult}
                )
            )
    """
    return sql