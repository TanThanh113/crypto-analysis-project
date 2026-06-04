def get_select_ofi_hidden_orders_sql(symbol, config_data, orderbook_table, sentiment_table, onchain_table):
    """
    Generates Flink SQL to detect Order Flow Imbalance (OFI) and Hidden Liquidity.
    UPGRADED: Confirms stealth accumulation/distribution using Macro Sentiment (OI Delta) 
    and On-chain Whale flows. Filters out random orderbook noise.
    """
    params = config_data['symbols'].get(symbol.upper(), config_data.get('default'))
    
    ofi_window = params.get('ofi_window_seconds', 10)
    delta_thresh = params.get('ofi_delta_usd_threshold', 500000) 

    sql = f"""
        WITH ob_window AS (
            SELECT 
                window_start, window_time, symbol,
                FIRST_VALUE(best_bid_price) AS open_price, 
                LAST_VALUE(best_bid_price) AS close_price,
                FIRST_VALUE(bid_vol_1pct_usd) AS open_bid_vol, 
                FIRST_VALUE(ask_vol_1pct_usd) AS open_ask_vol,
                LAST_VALUE(bid_vol_1pct_usd) AS close_bid_vol, 
                LAST_VALUE(ask_vol_1pct_usd) AS close_ask_vol
            
            FROM TABLE(TUMBLE(TABLE {orderbook_table}, DESCRIPTOR(ob_ts), INTERVAL '{ofi_window}' SECOND))
            WHERE symbol = '{symbol}'
            GROUP BY window_start, window_time, symbol
        ),
        ofi_calc AS (
            SELECT 
                window_time, symbol, open_price, close_price,
                (close_price - open_price) / open_price * 100 AS price_change_pct,
                (close_bid_vol - open_bid_vol) AS bid_delta_usd,
                (close_ask_vol - open_ask_vol) AS ask_delta_usd
            FROM ob_window
        )

        SELECT 
            'ORDER_FLOW_IMBALANCE' AS alert_type,
            O.symbol,
            CASE 
                -- GOD MODE DISTRIBUTION: Sideways + Bids pulled + Asks stacked + OI Spiking + Whale INFLOW
                WHEN O.bid_delta_usd <= -{delta_thresh} AND O.ask_delta_usd >= {delta_thresh} 
                     AND S.oi_delta_pct > 1.0 AND C.tx_type = 'INFLOW' THEN
                    '🩸 GOD MODE DISTRIBUTION (OFI): Price flat, but Bid Wall lost $' || CAST(ROUND(ABS(O.bid_delta_usd), 0) AS STRING) || 
                    '! Retail FOMO (OI: +' || CAST(S.oi_delta_pct AS STRING) || '%) met with Whale INFLOW. Lethal DUMP Imminent!'
                
                -- GOD MODE ACCUMULATION: Sideways + Asks pulled + Bids stacked + OI Spiking + Whale OUTFLOW
                WHEN O.bid_delta_usd >= {delta_thresh} AND O.ask_delta_usd <= -{delta_thresh} 
                     AND S.oi_delta_pct > 1.0 AND C.tx_type = 'OUTFLOW' THEN
                    '🧲 GOD MODE ACCUMULATION (OFI): Price flat, but Ask Wall lost $' || CAST(ROUND(ABS(O.ask_delta_usd), 0) AS STRING) || 
                    '! Market building positions (OI: +' || CAST(S.oi_delta_pct AS STRING) || '%) + Whale OUTFLOW. PUMP Imminent!'
                
                -- STANDARD MODE
                WHEN O.bid_delta_usd <= -{delta_thresh} AND O.ask_delta_usd >= {delta_thresh} THEN
                    '🩸 STANDARD DISTRIBUTION: Orderbook shifting to Sell side. Careful.'
                ELSE 
                    '🧲 STANDARD ACCUMULATION: Orderbook shifting to Buy side. Careful.'
            END AS alert_message,
            O.window_time AS event_time
            
        FROM ofi_calc AS O
        
        LEFT JOIN {sentiment_table} AS S
            ON O.symbol = S.symbol AND S.sent_ts BETWEEN O.window_time - INTERVAL '10' MINUTE AND O.window_time
        LEFT JOIN {onchain_table} AS C
            ON O.symbol = C.symbol AND C.chain_ts BETWEEN O.window_time - INTERVAL '1' HOUR AND O.window_time
            
        WHERE 
            ABS(O.price_change_pct) < 0.1
            AND 
            (
                (O.bid_delta_usd <= -{delta_thresh} AND O.ask_delta_usd >= {delta_thresh})
                OR 
                (O.bid_delta_usd >= {delta_thresh} AND O.ask_delta_usd <= -{delta_thresh})
            )
    """
    return sql