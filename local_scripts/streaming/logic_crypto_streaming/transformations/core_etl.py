# -*- coding: utf-8 -*-

def create_view_candlesticks(table_env, source_trades):
    table_env.execute_sql(f"""
        CREATE TEMPORARY VIEW v_candlesticks AS
        SELECT 
            window_start, 
            window_end, 
            window_time, 
            symbol,
            LAST_VALUE(trade_id) as trade_id,
            FIRST_VALUE(price) as open_price,
            MAX(price) as high_price,
            MIN(price) as low_price,
            LAST_VALUE(price) as close_price,
            SUM(quantity) as volume,
            SUM(price * quantity) / SUM(quantity) as VWAP
        FROM TABLE(
            TUMBLE(TABLE {source_trades}, DESCRIPTOR(trade_ts), INTERVAL '1' MINUTE)
        )
        GROUP BY 
            window_start,
            window_end, 
            window_time, 
            symbol
    """)

def get_insert_raw_data_sql(source_trades, sink_iceberg_trades):
    return f"""
        INSERT INTO {sink_iceberg_trades}
        SELECT 
            symbol, trade_id, price, quantity, event_time, trade_time,
            DATE_FORMAT(trade_ts, 'yyyy-MM-dd') as dt,
            DATE_FORMAT(trade_ts, 'HH') as hr
        FROM {source_trades}
    """

def get_insert_raw_candlestick(sink_iceberg_candles):
    return f"""
        INSERT INTO {sink_iceberg_candles}
        SELECT 
            symbol, trade_id, open_price, high_price, low_price, close_price, volume, VWAP, sma20,
            sma20 + (sd20 * 2) AS upper_band,
            sma20 - (sd20 * 2) AS lower_band,
            DATE_FORMAT(window_start, 'yyyy-MM-dd') as dt
        FROM (
            SELECT 
                window_start, window_end, symbol, trade_id, open_price, high_price, low_price, close_price, volume, VWAP,
                AVG(close_price) OVER (
                    PARTITION BY symbol 
                    ORDER BY window_time 
                    ROWS BETWEEN 19 PRECEDING AND CURRENT ROW
                ) as sma20,
                STDDEV_POP(close_price) OVER (
                    PARTITION BY symbol 
                    ORDER BY window_time 
                    ROWS BETWEEN 19 PRECEDING AND CURRENT ROW
                ) as sd20
            FROM v_candlesticks
        )
        WHERE symbol IS NOT NULL AND close_price IS NOT NULL
    """

def get_insert_candlestick_bb_sql(bq_sink):
    return f"""
    INSERT INTO {bq_sink}
    SELECT 
        window_start, window_end, symbol, trade_id, open_price, high_price, low_price, close_price, volume, VWAP, sma20,
        sma20 + (sd20 * 2) AS upper_band,
        sma20 - (sd20 * 2) AS lower_band
    FROM (
        SELECT 
            *,
            AVG(close_price) OVER (
                PARTITION BY symbol 
                ORDER BY window_time 
                ROWS BETWEEN 19 PRECEDING AND CURRENT ROW
            ) as sma20,
            STDDEV_POP(close_price) OVER (
                PARTITION BY symbol 
                ORDER BY window_time 
                ROWS BETWEEN 19 PRECEDING AND CURRENT ROW
            ) as sd20
        FROM v_candlesticks
    )
    WHERE symbol IS NOT NULL AND close_price IS NOT NULL
    """