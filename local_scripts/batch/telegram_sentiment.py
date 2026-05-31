# -*- coding: utf-8 -*-
import os
import re
import json
import asyncio
import logging
import random
import argparse
from datetime import datetime, timezone
import sys

import pandas as pd
import nltk
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import FloodWaitError
from telethon.tl.types import MessageMediaPhoto, MessageMediaDocument
from dotenv import load_dotenv
from nltk.sentiment.vader import SentimentIntensityAnalyzer

from save_dataframe_to_parquet import save_dataframe_to_parquet

#-----------------------------------------------------------------------------
# CONFIGURATION LOGGING & ENV & NLTK(VADER)
#-----------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    stream=sys.stdout
)

load_dotenv()

OUTPUT_DIR = os.environ.get("OUTPUT_DIR", "output_data/telegram")

# Scoring coefficient
WEIGHT_VIEWS = 0.01
WEIGHT_FORWARDS = 5.0
WEIGHT_REPLIES = 10.0
WEIGHT_REACTIONS = 2.0

# Regex Patterns
CASHTAG_REGEX = r"\$[A-Za-z0-9]+"
HASHTAG_REGEX = r"\#[A-Za-z0-9_]+"
URL_REGEX = r"(https?://[^\s]+)"
FINANCIAL_NUMBER_REGEX = r"(\$\d+[kKmMbB]?|\d+(\.\d+)?%)"

BTC_KEYWORDS = {"btc", "bitcoin", "$btc"} # Keywords for Bitcoin
ETH_KEYWORDS = {"eth", "ethereum", "$eth"} # Keywords for Ethereum
BULLISH_WORDS = {"buy", "bull", "bullish", "breakout", "pump", "moon", "long", "accumulate"} # Keywords for Bullish
BEARISH_WORDS = {"sell", "bear", "bearish", "dump", "liquidation", "crash", "panic", "short"} # Keywords for Bearish

TOPIC_KEYWORDS = {
    "AIRDROP_PROMO": {"airdrop", "giveaway", "claim", "whitelist", "presale"},
    "REGULATION": {"sec", "etf", "lawsuit", "court", "banned", "gensler", "regulation", "gov"},
    "HACK_SCAM": {"hack", "exploit", "stolen", "phishing", "rug", "scam", "compromised"},
    "TECH_ANALYSIS": {"support", "resistance", "rsi", "ma", "fibonacci", "chart", "breakout"},
    
    # ADD THIS GROUP TO CATCH MACRO NEWS & CONSPIRACY THEORIES (UFO, War, Politics...)
    "MACRO_POLITICS": {"ufo", "alien", "war", "debt", "president", "doj", "election", "biden", "trump", "putin", "gdp"}
}

SCHEMA_RAW = {
    "message_id": "int64", "date": "string", "datetime": "string", "channel": "string", "text": "string",
    "nlp_compound": "float64", "weighted_sentiment": "float64", "signal_type": "string", "coin_focus": "string", "topic": "string",
    "views": "int64", "forwards": "int64", "replies": "int64", "reactions": "int64", "engagement_score": "float64", "importance": "string",
    "word_count": "int64", "financial_mentions_count": "int64", "hour_of_day": "int64", "day_of_week": "string", "is_weekend": "bool",
    "cashtags": "string", "hashtags": "string", "urls": "string", "has_media": "bool", "media_type": "string", "is_forward": "bool", "message_url": "string",
    
    # Metadata
    "source": "string", "run_id": "string", "ingestion_time": "datetime64[ns, UTC]", 
    "year": "string", "month": "string", "day": "string"
}

SCHEMA_SUMMARY = {
    "channel": "string", "coin_focus": "string", "total_messages": "int64", 
    "total_views": "int64", "total_reactions": "int64", "avg_sentiment": "float64", 
    "weighted_sentiment": "float64", "bullish_posts": "int64", "bearish_posts": "int64",
    
    # Metadata
    "source": "string", "run_id": "string", "ingestion_time": "datetime64[ns, UTC]", 
    "year": "string", "month": "string", "day": "string"
}
#-----------------------------------------------------------------------------
# Initializing AI and "Teaching" AI to Understand Crypto Slang (Massive Upgrade)
#-----------------------------------------------------------------------------
# Download the Lexicon VADER NLP model for the first time and setup analyzer
def setup_nltk_analyzer():
    try:
        nltk.data.find('sentiment/vader_lexicon.zip')
    except LookupError:
        logging.info("⏳ Downloading VADER lexicon...")
        nltk.download('vader_lexicon', quiet=True)
    
    analyzer = SentimentIntensityAnalyzer()
    crypto_lexicon = {
        "hodl": 3.5, "moon": 3.5, "ath": 3.0, "pump": 2.5, "bullish": 2.5, "buy": 2.0, "breakout": 2.5, 
        "fud": -3.0, "rekt": -3.5, "dump": -3.0, "bearish": -2.5, "sell": -2.0, "liquidation": -3.0,
        "rug": -4.0, "scam": -4.0, "hack": -4.0, "crash": -4.0
    }
    analyzer.lexicon.update(crypto_lexicon)
    return analyzer

def clean_text(text):
    if not text: return ""
    text = re.sub(URL_REGEX, "", text)
    return re.sub(r"\s+", " ", text).strip()

# Label the coin
def detect_coin(text):
    t = text.lower()
    has_btc = any(k in t for k in BTC_KEYWORDS)
    has_eth = any(k in t for k in ETH_KEYWORDS)
    if has_btc and has_eth: return "BTC_ETH"
    if has_btc: return "BTC"
    if has_eth: return "ETH"
    return "GENERAL"

# Label the signal
def detect_signal(text):
    t = text.lower()
    if any(k in t for k in BULLISH_WORDS): return "BULLISH"
    if any(k in t for k in BEARISH_WORDS): return "BEARISH"
    return "NEUTRAL"

# Extract the topic
def extract_topic(text):
    t = text.lower()
    for topic, keywords in TOPIC_KEYWORDS.items():
        if any(k in t for k in keywords):
            return topic
    return "GENERAL_NEWS"

# Compute engagement score
def calc_engagement(views, forwards, replies, reactions):
    score = (views * WEIGHT_VIEWS) + (forwards * WEIGHT_FORWARDS) + (replies * WEIGHT_REPLIES) + (reactions * WEIGHT_REACTIONS)
    return max(score, 1.0)

# Classify the importance
def classify_importance(score):
    if score >= 10000: return "VIRAL"
    if score >= 3000: return "HIGH"
    if score >= 1000: return "MEDIUM"
    return "LOW"

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

#-----------------------------------------------------------------------------
# TELEGRAM SCRAPER
#-----------------------------------------------------------------------------
async def scrape_channel(client, channel, limit, analyzer, run_id):
    await asyncio.sleep(random.uniform(1, 5))
    logging.info(f"📥 Start scratching {channel}...")
    rows = []
    
    now = datetime.utcnow()
    year, month, day = now.strftime("%Y"), now.strftime("%m"), now.strftime("%d")
    try:
        async for message in client.iter_messages(channel, limit=limit):
            if not message: continue
            
            raw_text = message.text or ""
            if not raw_text and message.media:
                raw_text = "[Media Only]"
            elif not raw_text:
                continue

            cleaned_text = clean_text(raw_text)
            date_utc = message.date.astimezone(timezone.utc) if message.date else datetime.utcnow()
            
            # --- NLP & Sentiment ---
            sentiment = analyzer.polarity_scores(cleaned_text) # Cleaned text
            views = getattr(message, 'views', 0) or 0 # Number of views
            forwards = getattr(message, 'forwards', 0) or 0 # Number of forwards
            replies = message.replies.replies if message.replies else 0 # Number of replies
            # Total reactions
            reactions = sum(r.count for r in message.reactions.results) if getattr(message, 'reactions', None) and getattr(message.reactions, 'results', None) else 0
            
            eng_score = calc_engagement(views, forwards, replies, reactions) # Compute engagement score
            
            # --- DATA ENRICHMENT ---
            word_count = len(cleaned_text.split())
            financial_mentions = len(re.findall(FINANCIAL_NUMBER_REGEX, raw_text))
            hour_of_day = date_utc.hour
            day_of_week = date_utc.strftime("%A")
            is_weekend = date_utc.weekday() >= 5
            topic = extract_topic(cleaned_text)

            # --- MEDIA ---
            media_type = None
            if isinstance(message.media, MessageMediaPhoto): media_type = "PHOTO"
            elif isinstance(message.media, MessageMediaDocument): media_type = "DOCUMENT"

            rows.append({
                "message_id": message.id,
                "date": date_utc.strftime("%Y-%m-%d"),
                "datetime": date_utc.strftime("%Y-%m-%d %H:%M:%S"),
                "channel": channel,
                "text": cleaned_text,
                
                # NLP
                "nlp_compound": sentiment["compound"],
                "weighted_sentiment": sentiment["compound"] * eng_score,
                "signal_type": detect_signal(cleaned_text),
                "coin_focus": detect_coin(cleaned_text),
                "topic": topic, # ENRICHED
                
                # Engagement
                "views": views,
                "forwards": forwards,
                "replies": replies,
                "reactions": reactions,
                "engagement_score": eng_score,
                "importance": classify_importance(eng_score),
                
                # Metadata & Enrichment
                "word_count": word_count, # ENRICHED
                "financial_mentions_count": financial_mentions, # ENRICHED
                "hour_of_day": hour_of_day, # ENRICHED
                "day_of_week": day_of_week, # ENRICHED
                "is_weekend": is_weekend, # ENRICHED
                
                # Tags
                "cashtags": json.dumps(list(set(re.findall(CASHTAG_REGEX, cleaned_text)))),
                "hashtags": json.dumps(list(set(re.findall(HASHTAG_REGEX, cleaned_text)))),
                "urls": json.dumps(list(set(re.findall(URL_REGEX, raw_text)))),
                
                "has_media": bool(message.media),
                "media_type": media_type,
                "is_forward": bool(message.fwd_from),
                "message_url": f"https://t.me/{channel}/{message.id}",

                # Metadata
                "source": "telegram_api",
                "run_id": run_id,
                "ingestion_time": now,
                "year": year,
                "month": month,
                "day": day
            })
            
    except FloodWaitError as e:
        logging.warning(f"⏳ Subject to Rate Limit {channel}. Sleep {e.seconds}s...")
        await asyncio.sleep(e.seconds)
    except Exception as e:
        logging.error(f"❌ Error at {channel}: {e}")
        
    logging.info(f"✅ Collected {len(rows)} posts from {channel}")
    return rows

# =============================================================================
# SUMMARY TABLE
# =============================================================================

def build_summary(df, run_id):
    if df.empty:
        return pd.DataFrame()
    summary = df.groupby(["channel", "coin_focus"]).agg(
        total_messages=("message_id", "count"),
        total_views=("views", "sum"),
        total_reactions=("reactions", "sum"),
        avg_sentiment=("nlp_compound", "mean"),
        weighted_sentiment=("weighted_sentiment", "mean"),
        bullish_posts=("signal_type",lambda x: (x == "BULLISH").sum()),
        bearish_posts=("signal_type",lambda x: (x == "BEARISH").sum())
    ).reset_index()

    now = datetime.utcnow()
    summary["source"] = "telegram_api"
    summary["run_id"] = run_id
    summary["ingestion_time"] = now
    summary["year"] = now.strftime("%Y")
    summary["month"] = now.strftime("%m")
    summary["day"] = now.strftime("%d")

    return summary

#-----------------------------------------------------------------------------
# PIPELINE
#-----------------------------------------------------------------------------
async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=300)
    parser.add_argument("--manager", type=str, choices=["iceberg", "hive"], default="hive")
    args = parser.parse_args()

    api_id = os.getenv("API_ID")
    api_hash = os.getenv("API_HASH")
    session_str = os.getenv("TELEGRAM_SESSION_STRING")

    if not all([api_id, api_hash, session_str]):
        logging.error("❌ Missing Telegram API configuration in .env")
        return

    channels = [
        "cointelegraph", "watcherguru", "wublockchainenglish",
        "binance_announcements", "WhaleAlert", "cryptosignals", "fatpigsignals"
    ]

    analyzer = setup_nltk_analyzer()

    run_id = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    
    # Connect Telethon
    try:
        safe_api_id = int(api_id)
    except ValueError:
        logging.error("❌ CRITICAL ERROR: API_ID is not a valid integer! Please check Google Secret Manager.")
        sys.exit(1)
        
    try:
        client = TelegramClient(StringSession(session_str), safe_api_id, api_hash)
        await client.start()
    except Exception as e:
        logging.error("❌ CRITICAL ERROR: Failed to start TelegramClient! Please check API_HASH or Session String in Secret Manager.")
        sys.exit(1)
    
    # Extremely fast multi-threaded scraping
    logging.info("🚀 Start a multi-threaded ETL process with Data Enrichment...")
    tasks = [scrape_channel(client, channel, args.limit, analyzer, run_id) for channel in channels]
    results = await asyncio.gather(*tasks)
    
    await client.disconnect()

    # Processing results
    all_rows = [row for channel_data in results for row in channel_data]
    if not all_rows:
        logging.error("❌ No data was collected..")
        return

    raw_df = pd.DataFrame(all_rows)
    summary_df = build_summary(raw_df, run_id)

    raw_df = enforce_schema(raw_df, SCHEMA_RAW)
    summary_df = enforce_schema(summary_df, SCHEMA_SUMMARY)

    raw_output_dir = f"{OUTPUT_DIR}/raw"
    summary_output_dir = f"{OUTPUT_DIR}/summary"

    if args.manager == "iceberg":
        save_dataframe_to_parquet(raw_df, raw_output_dir, file_prefix="telegram_raw", partition_cols=None)
        if not summary_df.empty:
            save_dataframe_to_parquet(summary_df, summary_output_dir, file_prefix="telegram_summary", partition_cols=None)
    else:
        save_dataframe_to_parquet(
            raw_df, raw_output_dir, file_prefix="telegram_raw", 
            partition_cols=["channel", "year", "month", "day"]
        )
        if not summary_df.empty:
            save_dataframe_to_parquet(
                summary_df, summary_output_dir, file_prefix="telegram_summary", 
                partition_cols=["channel", "year", "month", "day"]
            )

    # --- Print ---
    print("\n" + "="*50)
    print("📊 Subject Classification Report (TOPICS)")
    print("="*50)
    topic_summary = raw_df['topic'].value_counts().reset_index()
    topic_summary.columns = ['Topic', 'Count of Posts']
    print(topic_summary.to_string(index=False))

    print("\n" + "="*50)
    print("🔥 TOP ARTICLES WITH THE HIGHEST ENGAGEMENT")
    print("="*50)
    top_posts = raw_df.nlargest(3, "engagement_score")
    for _, row in top_posts.iterrows():
        print(f"\n📢 [{row['channel'].upper()}] - Subject: {row['topic']} | Date: {row['day_of_week']} (Weekend: {row['is_weekend']})")
        print(f"💰 Financial data mentioned: {row['financial_mentions_count']} phrase | Length: {row['word_count']} words")
        print(f"👀 View: {row['views']} | Sentiment: {row['nlp_compound']:.2f}")
        print(f"📝 {row['text'][:150]}...")

if __name__ == '__main__':

    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    asyncio.run(main())