# -*- coding: utf-8 -*-
import os
import re
import time
import random
import hashlib
import logging
import argparse
import requests
import pandas as pd
import nltk
import sys

from datetime import datetime, timezone
from nltk.sentiment.vader import SentimentIntensityAnalyzer
from langdetect import detect, LangDetectException

from save_dataframe_to_parquet import save_dataframe_to_parquet

#------------------------------------------------------------------------------
# CONFIGURATION LOGGING & ENV
#------------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    stream=sys.stdout
)

#------------------------------------------------------------------------------
# DOWNLOADING LIBRARY VADER
#------------------------------------------------------------------------------
try:
    nltk.data.find('sentiment/vader_lexicon.zip')
except LookupError:
    logging.info("⏳ Loading the Lexicon VADER NLP model for the first time....")
    nltk.download('vader_lexicon', quiet=True)
# =============================================================================
# NLP MODEL
# =============================================================================
# Initializing AI and "Teaching" AI to Understand Crypto Slang (Massive Upgrade)
analyzer = SentimentIntensityAnalyzer()
crypto_lexicon = {
    'hodl': 3.5, 'moon': 3.5, 'ath': 3.0, 'pump': 2.5, 'bull': 2.5, 'bullish': 2.5, 'buy': 2.0,
    'fud': -3.0, 'rekt': -3.5, 'dump': -3.0, 'bear': -2.5, 'bearish': -2.5, 'sell': -2.0,
    'scam': -4.0, 'rug': -4.0, 'ponzi': -4.0, 'hack': -4.0, 'dip': -1.0,'liquidation': -3.0,
    'etf': 2.5, 'blackrock': 2.0, 'whale': 1.5
}
analyzer.lexicon.update(crypto_lexicon)

# =============================================================================
# CONSTANTS
# =============================================================================
OUTPUT_DIR = os.environ.get("OUTPUT_DIR", "output_data/reddit")

# All Reddit API requests are blocked by Reddit, so we need to use a browser to avoid being blocked.
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/118.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Safari/605.1.15'
]

BTC_KEYWORDS = [
    "btc", "bitcoin", "satoshi"
]

ETH_KEYWORDS = [
    "eth", "ethereum", "vitalik"
]

EVENT_PATTERNS = {
    "ETF": ["etf"],
    "SEC": ["sec", "lawsuit"],
    "HACK": ["hack", "exploit"],
    "WHALE": ["whale"],
    "LIQUIDATION": ["liquidation", "rekt"],
    "FED": ["fed", "powell", "rate cut"],
    "BLACKROCK": ["blackrock"],
    "BULLRUN": ["bullrun", "ath", "new high"],
    "BEARMARKET": ["bear market", "crash", "dump"]
}

SUBREDDIT_WEIGHTS = {"Bitcoin": 1.5, "Ethereum": 1.5, "ethtrader": 1.2, "CryptoCurrency": 1.0}

SCHEMA_RAW = {
    "post_id": "string", "subreddit": "string", "title": "string", "body": "string", 
    "full_text": "string", "author": "string", "created_utc": "string", "score": "int64", 
    "comments": "int64", "engagement_velocity": "float64", "interaction_weight": "float64", 
    "final_weight": "float64", "sentiment_compound": "float64", "weighted_sentiment": "float64", 
    "asset": "string", "event_tags": "string", "is_viral": "bool", "url": "string", 
    
    "source": "string", "run_id": "string", "ingestion_time": "datetime64[ns, UTC]", 
    "year": "string", "month": "string", "day": "string"
}

SCHEMA_SUMMARY = {
    "datetime": "string", "date": "string", "subreddit": "string", "asset": "string", 
    "total_posts": "int64", "bullish_ratio": "float64", "bearish_ratio": "float64", 
    "avg_sentiment": "float64", "weighted_sentiment": "float64", "viral_post_count": "int64", 
    "etf_mentions": "int64", "hack_mentions": "int64", "whale_mentions": "int64", 
    
    "source": "string", "run_id": "string", "ingestion_time": "datetime64[ns, UTC]", 
    "year": "string", "month": "string", "day": "string"
}
# =============================================================================
# HELPERS
# =============================================================================
# Only filter articles in English to reduce noise.
def safe_detect_language(text):
    try:
        return detect(text)
    except LangDetectException:
        return "unknown"
# Generate a hash code to mark the post.
def generate_content_hash(text):
    return hashlib.md5(text.encode("utf-8")).hexdigest()
# Mark which coin this post belongs to.
def detect_asset(text):
    text = text.lower()
    btc_score = sum(k in text for k in BTC_KEYWORDS)
    eth_score = sum(k in text for k in ETH_KEYWORDS)

    if btc_score > eth_score and btc_score > 0:
        return "BTC"

    if eth_score > btc_score and eth_score > 0:
        return "ETH"
    return "GENERAL"

# Add tags to that post.
def extract_event_tags(text):
    text = text.lower()
    tags = []
    for tag, patterns in EVENT_PATTERNS.items():
        if any(p in text for p in patterns):
            tags.append(tag)
    return ",".join(tags)

# Time decomposition (new articles will be more valuable than old ones)
def calculate_time_decay(created_dt):
    now = datetime.now(timezone.utc)
    hours_old = max((now - created_dt).total_seconds() / 3600, 1)
    # Inverse power function
    return 1 / (hours_old ** 0.3)

def enforce_schema(df: pd.DataFrame, target_schema: dict) -> pd.DataFrame:
    for col in target_schema:
        if col not in df.columns:
            df[col] = None

    df = df[list(target_schema.keys())].copy()

    for col, dtype in target_schema.items():
        try:
            if "datetime" in dtype:
                df[col] = pd.to_datetime(df[col], utc=True)
            elif dtype == "float64":
                df[col] = pd.to_numeric(df[col], errors="coerce").astype("float64")
            elif dtype == "int64":
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype("int64")
            elif dtype == "bool":
                df[col] = df[col].astype(bool)
            else:
                df[col] = df[col].astype(dtype)
        except Exception as e:
            logging.warning(f"⚠️ Schema cast warning {col}: {e}")
    return df
# =============================================================================
# REDDIT FETCHER
# =============================================================================
def fetch_reddit_posts(subreddit_name="CryptoCurrency", limit=100):
    logging.info(f"📥 Scraping Sentiment from {subreddit_name}, (Limit: {limit} posts)...")

    # Because using this method, only 100 problems can be retrieved at a time.
    # However, Reddit also provides something called "after" (the last post on the page).
    # Therefore, we can use the pagination technique to obtain all 200 articles.
    posts = []
    after = None
    while len(posts) < limit:
        url = f"https://www.reddit.com/r/{subreddit_name}/hot.json?limit=100"
        if after:
            url += f"&after={after}"
        try:
            headers = {
                'User-Agent': random.choice(USER_AGENTS)
            }

            response = requests.get(url, headers=headers, timeout=30)
            if response.status_code != 200:
                logging.error(f"❌ Error fetching Reddit Data: {response.status_code}")
                break

            data = response.json()
            new_posts = data['data']['children']

            if not new_posts:
                logging.warning(f"✅ Running out of cards to scratch {subreddit_name}, length: {len(posts)}")
                break
            posts.extend(new_posts)
            after = data['data']['after']

            if not after: 
                logging.warning(f"✅ No more posts to fetch from {subreddit_name}, length: {len(posts)}")
                break
            time.sleep(random.uniform(1, 2))

        except Exception as e:
            logging.error(f"❌ Error fetching Reddit Data: {e}", exc_info=True)
            return []
    
    posts = posts[:limit]
    logging.info(f"✂️ The list has been finalized. {len(posts)} article for analysis.")
    return posts
    
# =============================================================================
# ANALYSIS
# =============================================================================

def analyze_subreddit(subreddit_name="CryptoCurrency", limit=200, run_id=""):
    # Fetch posts from Reddit
    posts = fetch_reddit_posts(subreddit_name, limit)
    
    if posts is None or len(posts) == 0:
        return pd.DataFrame(), pd.DataFrame()
    
    raw_rows = [] # Raw Data
    summary_metrics = {"BTC": [], "ETH": [], "GENERAL": []} # Summary Metrics
    seen_hashes = set() # Avoid duplicated posts
    subreddit_weight = SUBREDDIT_WEIGHTS.get(subreddit_name, 1.0) # Subreddit Weighting

    now = datetime.utcnow()
    year, month, day = now.strftime("%Y"), now.strftime("%m"), now.strftime("%d")

    for post in posts:
        try:
            pdata = post["data"]
            if pdata.get("stickied"): # Ignore stickied posts
                continue 

            title = pdata.get("title", "")
            body = pdata.get("selftext", "")
            if body in ["[removed]", "[deleted]"]: # Ignore removed posts
                continue

            full_text = f"{title}. {body}".strip()
            if len(full_text) < 20: # Ignore short posts
                continue

            # Language filter
            lang = safe_detect_language(full_text)
            if lang != "en": # Ignore non-English posts
                continue

            # Dedup (Avoid duplicated posts)
            content_hash = generate_content_hash(full_text)
            if content_hash in seen_hashes:
                continue
            seen_hashes.add(content_hash)
            
            # Asset classification (BTC, ETH, GENERAL)
            asset = detect_asset(full_text)

            # Event tags 
            event_tags = extract_event_tags(full_text)

            # Sentiment (Vader Sentiment Analysis)
            sentiment = analyzer.polarity_scores(full_text)
            compound_score = sentiment["compound"]

            # Metrics
            upvotes = pdata.get("score", 0) # Upvotes
            comments = pdata.get("num_comments", 0) # Comments
            created_ts = pdata.get("created_utc") # Created timestamp
            created_dt = datetime.fromtimestamp(
                created_ts,
                tz=timezone.utc
            ) # Convert to datetime (Calculate time decay)
            hours_old = max((datetime.now(timezone.utc) - created_dt).total_seconds() / 3600, 1) # Calculate time decay
            time_decay = calculate_time_decay(created_dt)
            engagement_velocity = ((upvotes + comments)/hours_old) # Calculate engagement velocity
            interaction_weight = ((upvotes * 1.0) + (comments * 3.0))  # Calculate interaction weight
            final_weight = (interaction_weight * time_decay * subreddit_weight) # Calculate final weight
            weighted_sentiment = compound_score * final_weight # Calculate weighted sentiment

            # URL (Source url for the post)
            permalink = pdata.get("permalink", "")
            reddit_url = f"https://reddit.com{permalink}"

            # Viral detection (tag is_viral)
            is_viral = engagement_velocity > 100

            # Save RAW row
            raw_rows.append({
                "post_id": pdata.get("id"),
                "subreddit": subreddit_name,
                "title": title,
                "body": body,
                "full_text": full_text,
                "author": pdata.get("author"),
                "created_utc": created_dt.isoformat(),
                "score": upvotes,
                "comments": comments,
                "engagement_velocity": round(engagement_velocity, 2),
                "interaction_weight": round(interaction_weight, 2),
                "final_weight": round(final_weight, 4),
                "sentiment_compound": compound_score,
                "weighted_sentiment": weighted_sentiment,
                "asset": asset,
                "event_tags": event_tags,
                "is_viral": is_viral,
                "url": reddit_url,

                # Metadata
                "source": "reddit_json_scraping", 
                "run_id": run_id, 
                "ingestion_time": now,
                "year": year, 
                "month": month, 
                "day": day
            })
            summary_metrics[asset].append({
                "sentiment": compound_score,
                "weighted_sentiment": weighted_sentiment,
                "interaction_weight": interaction_weight,
                "is_viral": is_viral,
                "event_tags": event_tags
            })
        except Exception as e:
            logging.error(f"❌ Analysis Error: {e}")
    # =========================================================================
    # SUMMARY FEATURES
    # =========================================================================
    summary_rows = []
    current_time = datetime.utcnow()
    for asset, rows in summary_metrics.items():
        if not rows:
            continue

        sentiments = [r["sentiment"] for r in rows]
        weighted_scores = [r["weighted_sentiment"] for r in rows]
        bullish_count = len([s for s in sentiments if s > 0.05])
        bearish_count = len([s for s in sentiments if s < -0.05])
        viral_count = len([r for r in rows if r["is_viral"]])
        total_rows = len(rows)
        etf_mentions = sum("ETF" in r["event_tags"] for r in rows)
        hack_mentions = sum("HACK" in r["event_tags"] for r in rows)
        whale_mentions = sum("WHALE" in r["event_tags"] for r in rows)
        summary_rows.append({
            "datetime": current_time.strftime("%Y-%m-%d %H:%M:%S"),
            "date": current_time.strftime("%Y-%m-%d"),
            "subreddit": subreddit_name,
            "asset": asset,
            "total_posts": total_rows,
            "bullish_ratio": round(bullish_count / total_rows, 4),
            "bearish_ratio": round(bearish_count / total_rows, 4),
            "avg_sentiment": round(sum(sentiments) / total_rows, 4),
            "weighted_sentiment": round(sum(weighted_scores), 4),
            "viral_post_count": viral_count,
            "etf_mentions": etf_mentions,
            "hack_mentions": hack_mentions,
            "whale_mentions": whale_mentions,
            "source": "reddit_batch_pipeline",

            # Metadata
            "source": "reddit_batch_pipeline", 
            "run_id": run_id, 
            "ingestion_time": now,
            "year": year, 
            "month": month, 
            "day": day
        })
    raw_df = pd.DataFrame(raw_rows)
    summary_df = pd.DataFrame(summary_rows)
    logging.info(f"✅ [{subreddit_name}] "f"RAW={len(raw_df)} | "f"SUMMARY={len(summary_df)}")
    return raw_df, summary_df

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--manager", type=str, choices=["iceberg", "hive"], default="hive")
    args = parser.parse_args()

    subreddits = ["CryptoCurrency", "Bitcoin", "Ethereum", "ethtrader"]
    all_raw = []
    all_summary = []
    run_id = datetime.utcnow().strftime("%Y%m%d_%H%M%S")

    for sub in subreddits:
        raw_df, summary_df = analyze_subreddit(subreddit_name=sub, limit=args.limit, run_id=run_id)
        if not raw_df.empty: all_raw.append(raw_df)
        if not summary_df.empty: all_summary.append(summary_df)
        time.sleep(random.uniform(5, 10))

        time.sleep(random.uniform(5, 10))
    if not all_raw:
        logging.error("❌ No Reddit data collected.")
        return

    raw_final = pd.concat(all_raw, ignore_index=True)
    summary_final = pd.concat(all_summary, ignore_index=True)

    raw_final = enforce_schema(raw_final, SCHEMA_RAW)
    summary_final = enforce_schema(summary_final, SCHEMA_SUMMARY)

    raw_output_dir = f"{OUTPUT_DIR}/raw"
    summary_output_dir = f"{OUTPUT_DIR}/summary"

    if args.manager == "iceberg":
        save_dataframe_to_parquet(raw_final, raw_output_dir, file_prefix="reddit_raw", partition_cols=None)
        save_dataframe_to_parquet(summary_final, summary_output_dir, file_prefix="reddit_summary", partition_cols=None)
    else:
        save_dataframe_to_parquet(raw_final, raw_output_dir, file_prefix="reddit_raw", partition_cols=["subreddit", "asset", "year", "month", "day"])
        save_dataframe_to_parquet(
            summary_final, 
            summary_output_dir, 
            file_prefix="reddit_summary", 
            partition_cols=["subreddit", "asset", "year", "month", "day"]
        )

    # =========================================================================
    # QUICK REPORT
    # =========================================================================

    print("\n📊 REDDIT FEATURE SUMMARY")
    print(summary_final.to_string())
    print("\n🔥 TOP VIRAL POSTS")
    top_viral = raw_final.sort_values(by="engagement_velocity", ascending=False).head(5)
    for _, row in top_viral.iterrows():

        print(f"\n[{row['asset']}] "
            f"Velocity={row['engagement_velocity']} "
            f"| Sentiment={row['sentiment_compound']}"
        )
        print(row["title"][:200])

# =============================================================================
# ENTRYPOINT
# =============================================================================

if __name__ == "__main__":
    main()