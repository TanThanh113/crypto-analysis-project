# /app/batch/data_validator.py
# -*- coding: utf-8 -*-

import os
import glob
import sys
import argparse
import pandas as pd
import great_expectations as gx
import sys
import pyarrow.parquet as pq

import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s", stream=sys.stdout)

VALIDATION_RULES = {
    # BINANCE TRADES
    "binance_trades": [
        # Columns cannot be NULL.
        {"rule": "ExpectColumnValuesToNotBeNull", "kwargs": {"column": "symbol"}},
        {"rule": "ExpectColumnValuesToNotBeNull", "kwargs": {"column": "trade_id"}},
        {"rule": "ExpectColumnValuesToNotBeNull", "kwargs": {"column": "trade_ts"}},
        
        # The transaction value must be a reasonable positive number.
        {"rule": "ExpectColumnValuesToBeBetween", "kwargs": {"column": "price", "min_value": 0.0000001}},
        {"rule": "ExpectColumnValuesToBeBetween", "kwargs": {"column": "quantity", "min_value": 0.0000001}},
        {"rule": "ExpectColumnValuesToBeBetween", "kwargs": {"column": "quote_quantity", "min_value": 0.0000001}},
        
        # The transaction must be a True or False value.
        {"rule": "ExpectColumnValuesToNotBeNull", "kwargs": {"column": "is_buyer_maker"}},
    ],
    
    # MACRO INDICATORS & ETF (TIINGO)
    "macro_indicators_raw": [
        # Columns cannot be NULL.
        {"rule": "ExpectColumnValuesToNotBeNull", "kwargs": {"column": "symbol"}},
        {"rule": "ExpectColumnValuesToNotBeNull", "kwargs": {"column": "date"}},
        
        # Ensure correct macro classification
        {"rule": "ExpectColumnValuesToBeInSet", "kwargs": {"column": "asset_class", "value_set": ["macro"]}},
        
        # The transaction value must be a reasonable positive number.
        {"rule": "ExpectColumnValuesToBeBetween", "kwargs": {"column": "open", "min_value": 0.0000001}},
        {"rule": "ExpectColumnValuesToBeBetween", "kwargs": {"column": "high", "min_value": 0.0000001}},
        {"rule": "ExpectColumnValuesToBeBetween", "kwargs": {"column": "low", "min_value": 0.0000001}},
        {"rule": "ExpectColumnValuesToBeBetween", "kwargs": {"column": "close", "min_value": 0.0000001}},
        
        # Volume must be a positive number or zero.
        {"rule": "ExpectColumnValuesToBeBetween", "kwargs": {"column": "volume", "min_value": 0}},
    ],
    "etf_indicators_raw": [
        # Columns cannot be NULL.
        {"rule": "ExpectColumnValuesToNotBeNull", "kwargs": {"column": "symbol"}},
        {"rule": "ExpectColumnValuesToNotBeNull", "kwargs": {"column": "date"}},
        
        # Ensure correct ETF classification
        {"rule": "ExpectColumnValuesToBeInSet", "kwargs": {"column": "asset_class", "value_set": ["etf"]}},
        
        # The transaction value must be a reasonable positive number.
        {"rule": "ExpectColumnValuesToBeBetween", "kwargs": {"column": "open", "min_value": 0.0000001}},
        {"rule": "ExpectColumnValuesToBeBetween", "kwargs": {"column": "high", "min_value": 0.0000001}},
        {"rule": "ExpectColumnValuesToBeBetween", "kwargs": {"column": "low", "min_value": 0.0000001}},
        {"rule": "ExpectColumnValuesToBeBetween", "kwargs": {"column": "close", "min_value": 0.0000001}},

        # Volume must be a positive number or zero.
        {"rule": "ExpectColumnValuesToBeBetween", "kwargs": {"column": "volume", "min_value": 0}},
    ],

    # SENTIMENT (TELEGRAM & REDDIT)
    "telegram_raw": [
        # Columns cannot be NULL.
        {"rule": "ExpectColumnValuesToNotBeNull", "kwargs": {"column": "message_id"}},
        {"rule": "ExpectColumnValuesToNotBeNull", "kwargs": {"column": "channel"}},
        {"rule": "ExpectColumnValuesToNotBeNull", "kwargs": {"column": "text"}},
        
        # VADER emotional scores consistently range from -1 (Extremely negative) to 1 (Extremely positive).
        {"rule": "ExpectColumnValuesToBeBetween", "kwargs": {"column": "nlp_compound", "min_value": -1.0, "max_value": 1.0}},
        
        # The signal indicator is only allowed to be in these 3 states.
        {"rule": "ExpectColumnValuesToBeInSet", "kwargs": {"column": "signal_type", "value_set": ["BULLISH", "BEARISH", "NEUTRAL"]}},
        
        # View counts and comments must not be negative.
        {"rule": "ExpectColumnValuesToBeBetween", "kwargs": {"column": "views", "min_value": 0}},

        # The minimum interaction point is 1 point.
        {"rule": "ExpectColumnValuesToBeBetween", "kwargs": {"column": "engagement_score", "min_value": 0.99}},
    ],

    "reddit_raw": [
        # Columns cannot be NULL.
        {"rule": "ExpectColumnValuesToNotBeNull", "kwargs": {"column": "post_id"}},
        {"rule": "ExpectColumnValuesToNotBeNull", "kwargs": {"column": "subreddit"}},
        {"rule": "ExpectColumnValuesToNotBeNull", "kwargs": {"column": "full_text"}},
        
        # VADER emotional scores consistently range from -1 (Extremely negative) to 1 (Extremely positive).
        {"rule": "ExpectColumnValuesToBeBetween", "kwargs": {"column": "sentiment_compound", "min_value": -1.0, "max_value": 1.0}},
        
        # The number of comments and engagement velocity must not be negative.
        {"rule": "ExpectColumnValuesToBeBetween", "kwargs": {"column": "comments", "min_value": 0}},
        {"rule": "ExpectColumnValuesToBeBetween", "kwargs": {"column": "engagement_velocity", "min_value": 0}},
        
        # The asset classification is only allowed to be in these 3 states.
        {"rule": "ExpectColumnValuesToBeInSet", "kwargs": {"column": "asset", "value_set": ["BTC", "ETH", "GENERAL"]}},
    ],

    # DERIVATIVES & Risk of Risk (LIQUIDATION, FUNDING, OPTIONS)
    "liquidation_map": [
        # Columns cannot be NULL.
        {"rule": "ExpectColumnValuesToNotBeNull", "kwargs": {"column": "symbol"}},
        {"rule": "ExpectColumnValuesToBeBetween", "kwargs": {"column": "price_bucket", "min_value": 0.0000001}},
        
        # Total liquidation and hit count must not be negative.
        {"rule": "ExpectColumnValuesToBeBetween", "kwargs": {"column": "total_liq_usd_bucket", "min_value": 0}},
        {"rule": "ExpectColumnValuesToBeBetween", "kwargs": {"column": "hit_count", "min_value": 0}},

        # Rule for the weighted liquidation ratio, panic_norm and magnet_norm.
        {"rule": "ExpectColumnValuesToBeBetween", "kwargs": {"column": "weighted_liq_ratio", "min_value": -1.0, "max_value": 1.0}},
        {"rule": "ExpectColumnValuesToBeBetween", "kwargs": {"column": "panic_norm", "min_value": 0.0, "max_value": 1.0}},
        {"rule": "ExpectColumnValuesToBeBetween", "kwargs": {"column": "magnet_norm", "min_value": -1.0, "max_value": 1.0}},

        # The squeeze signal is only allowed to be in these 3 states.
        {"rule": "ExpectColumnValuesToBeInSet", "kwargs": {"column": "squeeze_signal", "value_set": ["SHORT_SQUEEZE_SETUP", "LONG_SQUEEZE_SETUP", "NEUTRAL"]}},
    ],
    "funding_rates": [
        # Columns cannot be NULL.
        {"rule": "ExpectColumnValuesToNotBeNull", "kwargs": {"column": "exchange"}},
        {"rule": "ExpectColumnValuesToNotBeNull", "kwargs": {"column": "symbol"}},
        
        # Spot and Mark prices must never be negative.
        {"rule": "ExpectColumnValuesToBeBetween", "kwargs": {"column": "mark_price", "min_value": 0.0000001}},
        {"rule": "ExpectColumnValuesToBeBetween", "kwargs": {"column": "spot_price", "min_value": 0.0000001}},
        
        # Note: API filtering: The difference between Spot and Futures prices (Basis %) rarely exceeds ±20%.
        # (Unless the floor collapses, this excessive deviation is usually an API error.)
        {"rule": "ExpectColumnValuesToBeBetween", "kwargs": {"column": "basis_pct", "min_value": -20.0, "max_value": 20.0}},
        
        # The arbitrage opportunity is only allowed to be in these 3 states.
        {"rule": "ExpectColumnValuesToBeInSet", "kwargs": {"column": "arbitrage_opportunity", "value_set": ["FAVOR_USDT_M", "FAVOR_COIN_M", "BALANCED"]}},
        
        # Note: Funding rates (Coin-M and USDT-M) rarely exceed ±10% per 8-hour period.
        # (This rule is to prevent Binance/Bybit from changing the API format from percentages to decimal numbers or vice versa.)
        {"rule": "ExpectColumnValuesToBeBetween", "kwargs": {"column": "funding_rate_coin", "min_value": -10.0, "max_value": 10.0}},
        {"rule": "ExpectColumnValuesToBeBetween", "kwargs": {"column": "funding_rate_usdt", "min_value": -10.0, "max_value": 10.0}},
    ],
    "deribit_options": [
        # Columns cannot be NULL.
        {"rule": "ExpectColumnValuesToNotBeNull", "kwargs": {"column": "instrument_name"}},
        {"rule": "ExpectColumnValuesToNotBeNull", "kwargs": {"column": "underlying"}},
        {"rule": "ExpectColumnValuesToNotBeNull", "kwargs": {"column": "expiry"}},
        
        # The option type must be either C (Call) or P (Put).
        {"rule": "ExpectColumnValuesToBeInSet", "kwargs": {"column": "option_type", "value_set": ["C", "P"]}},
        
        # The price levels (Strike, Index, Mark) must not be negative.
        {"rule": "ExpectColumnValuesToBeBetween", "kwargs": {"column": "strike", "min_value": 0.0000001}},
        {"rule": "ExpectColumnValuesToBeBetween", "kwargs": {"column": "index_price", "min_value": 0.0000001}},
        {"rule": "ExpectColumnValuesToBeBetween", "kwargs": {"column": "mark_price", "min_value": 0.0}},
        
        # Note: Implied Volatility (IV) is usually a positive number.
        # (Here, ExpectColumnValuesToBeBetween is used to filter out noise or errors caused by division by zero.)
        {"rule": "ExpectColumnValuesToBeBetween", "kwargs": {"column": "mark_iv", "min_value": 0}},
        {"rule": "ExpectColumnValuesToBeBetween", "kwargs": {"column": "mid_iv", "min_value": 0}},
        
        # The Delta of a Call Option ranges from 0 to 1, while that of a Put Option ranges from -1 to 0.
        {"rule": "ExpectColumnValuesToBeBetween", "kwargs": {"column": "delta", "min_value": -1.05, "max_value": 1.05}},
        
        # Open Interest must not be negative.
        {"rule": "ExpectColumnValuesToBeBetween", "kwargs": {"column": "open_interest", "min_value": 0}},
    ],

    # ON-CHAIN & EXCHANGE RESERVE
    "exchange_reserve": [
        # Columns cannot be NULL.
        {"rule": "ExpectColumnValuesToNotBeNull", "kwargs": {"column": "exchange"}},
        
        # Dự trữ trên chuỗi (On-chain) không được phép âm (DefiLlama và Arkham)
        {"rule": "ExpectColumnValuesToBeBetween", "kwargs": {"column": "actual_reserve_usd", "min_value": 0}},
        {"rule": "ExpectColumnValuesToBeBetween", "kwargs": {"column": "trade_volume_24h_usd", "min_value": 0}},
        
        {"rule": "ExpectColumnValuesToBeBetween", "kwargs": {"column": "reserve_dominance_pct", "min_value": 0.0, "max_value": 100.0}},
        {"rule": "ExpectColumnValuesToBeBetween", "kwargs": {"column": "trust_score", "min_value": 0.0, "max_value": 10.0}},
        
        # The risk of bank run and exchange concentration is only allowed to be in these 3 or 4 states.
        {"rule": "ExpectColumnValuesToBeInSet", "kwargs": {"column": "bank_run_risk", "value_set": ["SAFE", "MODERATE", "HIGH_RISK"]}},
        {"rule": "ExpectColumnValuesToBeInSet", "kwargs": {"column": "exchange_tier", "value_set": ["tier_1", "tier_2", "tier_3", "tier_4"]}},
    ],
    # STABLECOIN SUPPLY
    "stablecoin_supply": [
        # Columns cannot be NULL.
        {"rule": "ExpectColumnValuesToNotBeNull", "kwargs": {"column": "symbol"}},
        {"rule": "ExpectColumnValuesToNotBeNull", "kwargs": {"column": "price_usd"}},

        # The price of the stablecoin must never be negative.
        {"rule": "ExpectColumnValuesToBeBetween", "kwargs": {"column": "price_usd", "min_value": 0.0000001}},
        {"rule": "ExpectColumnValuesToBeBetween", "kwargs": {"column": "market_cap_usd", "min_value": 0.0000001}},

        # The price of the stablecoin must be between 95% and 105% of the market cap.
        {"rule": "ExpectColumnValuesToBeBetween", "kwargs": {"column": "price_usd", "min_value": 0.95, "max_value": 1.05}},
        
    ]
}

def main():
    parser = argparse.ArgumentParser(description="Universal Data Quality Validator")
    parser.add_argument("--dataset", type=str, required=True, help="Data name for looking up rules (vd: binance_trades, macro_indicators)")
    parser.add_argument("--file_pattern", type=str, required=True, help="Pattern find file (vd: tiingo_macro_raw_*.parquet)")
    args = parser.parse_args()

    OUTPUT_DIR = os.environ.get("OUTPUT_DIR", "output_data")
    search_path = os.path.join(OUTPUT_DIR, "**", args.file_pattern)
    files = glob.glob(search_path, recursive=True)

    if not files:
        logging.error(f"❌ No file found matching pattern: {args.file_pattern}")
        sys.exit(1)
    # Check if there is a rule for this dataset.
    if args.dataset not in VALIDATION_RULES:
        logging.warning(f"⚠️ Dataset '{args.dataset}' is not defined in the system. Skipping validation!")
        sys.exit(0) # Continue with the pass, as there is no rule for this dataset.
    rules = VALIDATION_RULES[args.dataset]

    # Create a Great Expectations Ephemeral
    context = gx.get_context(mode="ephemeral") # Initialize a "temporary" Great Expectations environment.

    # Load verb rules from the dictionary.
    suite = gx.ExpectationSuite(name=f"{args.dataset}_suite")
    for rule_def in rules:
        rule_name = rule_def["rule"]
        kwargs = rule_def["kwargs"]
        
        # Call the corresponding Expectation class from the gx.expectations library.
        ExpectationClass = getattr(gx.expectations, rule_name)
        suite.add_expectation(ExpectationClass(**kwargs))

    suite = context.suites.add(suite)
    
    # GE wraps data in its "batch" concept.
    datasource = context.data_sources.add_pandas(name="universal_source")
    data_asset = datasource.add_dataframe_asset(name="universal_asset")

    # BATCH DEFINITION & VALIDATION DEFINITION
    batch_definition = data_asset.add_batch_definition_whole_dataframe("universal_batch_def")

    validation_definition = gx.ValidationDefinition(
        name=f"{args.dataset}_validation",
        data=batch_definition,
        suite=suite
    )

    validation_definition = context.validation_definitions.add(validation_definition)
    pipeline_failed = False

    for file_to_check in files:
        logging.info(f"🔍 Checking file: {file_to_check} for dataset '{args.dataset}'")
        file_failed = False
        try:
            parquet_file = pq.ParquetFile(file_to_check)
            
            if parquet_file.metadata.num_rows == 0:
                logging.warning(f"⚠️ File {file_to_check} is empty, skipping...")
                continue

            chunk_idx = 0
            for batch in parquet_file.iter_batches(batch_size=100000):
                df_chunk = batch.to_pandas()
                if df_chunk.empty:
                    continue
                
                result = validation_definition.run(batch_parameters={"dataframe": df_chunk})
                if not result.success:
                    logging.error(f"❌ File '{file_to_check}' (Chunk {chunk_idx}) failed the validation!")

                    for res in result.results:
                        if not res.success:
                            col = res.expectation_config.kwargs.get("column", "Unknown")
                            rule = res.expectation_config.type
                            
                            unexpected_pct = res.result.get("unexpected_percent", "N/A")
                            if unexpected_pct != "N/A":
                                unexpected_pct = round(float(unexpected_pct), 2)
                                
                            logging.error(f"   ⚠️ Column '{col}' failed the rule '{rule}' ({unexpected_pct}%)")

                    file_failed = True
                    pipeline_failed = True
                    break
                    
            if not file_failed:
                logging.info(f"✅ File '{file_to_check}' passed the validation!")

        except Exception as e:
            logging.error(f"🚨 Critical error while reading or validating file {file_to_check}: {e}")
            pipeline_failed = True
            continue

    if pipeline_failed:
        logging.error(f"🚨 FAIL: The data '{args.dataset}' did not meet the quality criteria!")
        sys.exit(1)

    logging.info(f"🎉 GREAT: Data '{args.dataset}' passed the {len(rules)} quality test!")

if __name__ == "__main__":
    main()