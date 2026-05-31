# -*- coding: utf-8 -*-
"""
Reddit sentiment collector using Reddit RSS/Atom feeds instead of unauthenticated
reddit.com JSON endpoints.

Why this version exists:
- The old endpoint https://www.reddit.com/r/<subreddit>/hot.json can return HTTP 403.
- RSS/Atom feeds do not require a Reddit Developer App/OAuth credentials.
- This file keeps the same output shape as the original collector:
  reddit_raw_*.parquet and reddit_summary_*.parquet.

Usage:
  uv run reddit_sentiment_rss_test.py --manager iceberg --limit 20

If this test works, replace local_scripts/batch/reddit_sentiment.py with this file.
"""

import argparse
import hashlib
import logging
import os
import random
import re
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse

import nltk
import pandas as pd
import requests
from langdetect import LangDetectException, detect
from nltk.sentiment.vader import SentimentIntensityAnalyzer

from save_dataframe_to_parquet import save_dataframe_to_parquet

# -----------------------------------------------------------------------------
# LOGGING
# -----------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
)

# -----------------------------------------------------------------------------
# VADER
# -----------------------------------------------------------------------------
try:
    nltk.data.find("sentiment/vader_lexicon.zip")
except LookupError:
    logging.info("⏳ Loading the VADER lexicon for the first time...")
    nltk.download("vader_lexicon", quiet=True)

analyzer = SentimentIntensityAnalyzer()
crypto_lexicon = {
    "hodl": 3.5,
    "moon": 3.5,
    "ath": 3.0,
    "pump": 2.5,
    "bull": 2.5,
    "bullish": 2.5,
    "buy": 2.0,
    "fud": -3.0,
    "rekt": -3.5,
    "dump": -3.0,
    "bear": -2.5,
    "bearish": -2.5,
    "sell": -2.0,
    "scam": -4.0,
    "rug": -4.0,
    "ponzi": -4.0,
    "hack": -4.0,
    "dip": -1.0,
    "liquidation": -3.0,
    "etf": 2.5,
    "blackrock": 2.0,
    "whale": 1.5,
}
analyzer.lexicon.update(crypto_lexicon)

# -----------------------------------------------------------------------------
# CONSTANTS
# -----------------------------------------------------------------------------
OUTPUT_DIR = os.environ.get("OUTPUT_DIR", "output_data/reddit")

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) "
    "Gecko/20100101 Firefox/118.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/16.6 Safari/605.1.15",
]

BTC_KEYWORDS = ["btc", "bitcoin", "satoshi"]
ETH_KEYWORDS = ["eth", "ethereum", "vitalik"]

EVENT_PATTERNS = {
    "ETF": ["etf"],
    "SEC": ["sec", "lawsuit"],
    "HACK": ["hack", "exploit"],
    "WHALE": ["whale"],
    "LIQUIDATION": ["liquidation", "rekt"],
    "FED": ["fed", "powell", "rate cut"],
    "BLACKROCK": ["blackrock"],
    "BULLRUN": ["bullrun", "ath", "new high"],
    "BEARMARKET": ["bear market", "crash", "dump"],
}

SUBREDDIT_WEIGHTS = {
    "Bitcoin": 1.5,
    "Ethereum": 1.5,
    "ethtrader": 1.2,
    "CryptoCurrency": 1.0,
}

SCHEMA_RAW = {
    "post_id": "string",
    "subreddit": "string",
    "title": "string",
    "body": "string",
    "full_text": "string",
    "author": "string",
    "created_utc": "string",
    "score": "int64",
    "comments": "int64",
    "engagement_velocity": "float64",
    "interaction_weight": "float64",
    "final_weight": "float64",
    "sentiment_compound": "float64",
    "weighted_sentiment": "float64",
    "asset": "string",
    "event_tags": "string",
    "is_viral": "bool",
    "url": "string",
    "source": "string",
    "run_id": "string",
    "ingestion_time": "datetime64[ns, UTC]",
    "year": "string",
    "month": "string",
    "day": "string",
}

SCHEMA_SUMMARY = {
    "datetime": "string",
    "date": "string",
    "subreddit": "string",
    "asset": "string",
    "total_posts": "int64",
    "bullish_ratio": "float64",
    "bearish_ratio": "float64",
    "avg_sentiment": "float64",
    "weighted_sentiment": "float64",
    "viral_post_count": "int64",
    "etf_mentions": "int64",
    "hack_mentions": "int64",
    "whale_mentions": "int64",
    "source": "string",
    "run_id": "string",
    "ingestion_time": "datetime64[ns, UTC]",
    "year": "string",
    "month": "string",
    "day": "string",
}

ATOM_NS = {"atom": "http://www.w3.org/2005/Atom"}

# -----------------------------------------------------------------------------
# HELPERS
# -----------------------------------------------------------------------------
def safe_detect_language(text: str) -> str:
    try:
        return detect(text)
    except LangDetectException:
        return "unknown"


def generate_content_hash(text: str) -> str:
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def detect_asset(text: str) -> str:
    text = text.lower()
    btc_score = sum(k in text for k in BTC_KEYWORDS)
    eth_score = sum(k in text for k in ETH_KEYWORDS)

    if btc_score > eth_score and btc_score > 0:
        return "BTC"
    if eth_score > btc_score and eth_score > 0:
        return "ETH"
    return "GENERAL"


def extract_event_tags(text: str) -> str:
    text = text.lower()
    tags = []
    for tag, patterns in EVENT_PATTERNS.items():
        if any(pattern in text for pattern in patterns):
            tags.append(tag)
    return ",".join(tags)


def calculate_time_decay(created_dt: datetime) -> float:
    now = datetime.now(timezone.utc)
    hours_old = max((now - created_dt).total_seconds() / 3600, 1)
    return 1 / (hours_old ** 0.3)


def strip_html(text: str) -> str:
    if not text:
        return ""

    # Remove HTML tags from RSS content.
    text = re.sub(r"<[^>]+>", " ", text)
    # Remove common HTML entities roughly enough for sentiment extraction.
    replacements = {
        "&amp;": "&",
        "&lt;": "<",
        "&gt;": ">",
        "&quot;": '"',
        "&#39;": "'",
        "&apos;": "'",
        "&nbsp;": " ",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)

    text = re.sub(r"\s+", " ", text).strip()
    return text


def normalize_reddit_permalink(link: str) -> str:
    if not link:
        return ""

    parsed = urlparse(link)
    if parsed.path:
        return parsed.path
    return link


def parse_reddit_datetime(value: str | None) -> datetime:
    if not value:
        return datetime.now(timezone.utc)

    value = value.strip()

    # Atom usually uses ISO-8601: 2026-05-31T10:00:00+00:00 or ...Z
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        pass

    # RSS may use RFC 2822 dates.
    try:
        dt = parsedate_to_datetime(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return datetime.now(timezone.utc)


def find_text(entry: ET.Element, names: list[str]) -> str:
    for name in names:
        element = entry.find(name, ATOM_NS) if name.startswith("atom:") else entry.find(name)
        if element is not None and element.text:
            return element.text.strip()
    return ""


def find_link(entry: ET.Element) -> str:
    for link_el in entry.findall("atom:link", ATOM_NS):
        href = link_el.attrib.get("href")
        if href:
            return href

    link_el = entry.find("link")
    if link_el is not None and link_el.text:
        return link_el.text.strip()

    return ""


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
        except Exception as exc:
            logging.warning(f"⚠️ Schema cast warning {col}: {exc}")

    return df


# -----------------------------------------------------------------------------
# REDDIT RSS FETCHER
# -----------------------------------------------------------------------------
def fetch_reddit_posts(subreddit_name: str = "CryptoCurrency", limit: int = 100):
    logging.info(f"📥 Scraping Reddit RSS from r/{subreddit_name}, limit={limit}...")

    feed_urls = [
        f"https://old.reddit.com/r/{subreddit_name}/hot/.rss?limit={limit}",
        f"https://www.reddit.com/r/{subreddit_name}/hot/.rss?limit={limit}",
        f"https://old.reddit.com/r/{subreddit_name}/.rss?limit={limit}",
        f"https://www.reddit.com/r/{subreddit_name}/.rss?limit={limit}",
        f"https://old.reddit.com/r/{subreddit_name}/new/.rss?limit={limit}",
        f"https://www.reddit.com/r/{subreddit_name}/new/.rss?limit={limit}",
    ]

    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "application/atom+xml, application/rss+xml, application/xml;q=0.9, */*;q=0.8",
    }

    last_error = None

    for feed_url in feed_urls:
        try:
            logging.info(f"🌐 Fetching RSS feed: {feed_url}")
            response = requests.get(feed_url, headers=headers, timeout=30)

            if response.status_code != 200:
                last_error = f"HTTP {response.status_code} from {feed_url}"
                logging.warning(f"⚠️ Reddit RSS fetch failed: {last_error}")
                continue

            root = ET.fromstring(response.text)
            entries = root.findall("atom:entry", ATOM_NS)
            if not entries:
                # Fallback for non-namespaced feeds.
                entries = root.findall(".//entry")

            posts = []

            for entry in entries[:limit]:
                title = find_text(entry, ["atom:title", "title"])
                entry_id = find_text(entry, ["atom:id", "id"])
                updated_text = find_text(entry, ["atom:updated", "updated", "pubDate"])
                content_html = find_text(entry, ["atom:content", "content", "description"])
                author = find_text(entry, ["atom:author/atom:name", "author"])
                link = find_link(entry)

                body = strip_html(content_html)
                created_dt = parse_reddit_datetime(updated_text)

                full_text_for_hash = f"{title} {body} {link} {entry_id}".strip()
                post_id = hashlib.md5(full_text_for_hash.encode("utf-8")).hexdigest()[:16]

                # RSS does not reliably expose score/comment count.
                # Use score=1 so downstream weighting does not become zero.
                posts.append(
                    {
                        "data": {
                            "id": post_id,
                            "title": title,
                            "selftext": body,
                            "author": author or "unknown",
                            "created_utc": created_dt.timestamp(),
                            "score": 1,
                            "num_comments": 0,
                            "permalink": normalize_reddit_permalink(link),
                            "stickied": False,
                        }
                    }
                )

            if posts:
                logging.info(f"✅ Reddit RSS collected {len(posts)} posts from r/{subreddit_name}")
                return posts[:limit]

            last_error = f"No RSS entries found from {feed_url}"
            logging.warning(f"⚠️ {last_error}")

        except Exception as exc:
            last_error = str(exc)
            logging.warning(f"⚠️ Reddit RSS source failed: {feed_url} | {exc}", exc_info=True)
            continue

    raise RuntimeError(f"Reddit RSS fetch failed for r/{subreddit_name}. Last error: {last_error}")


# -----------------------------------------------------------------------------
# ANALYSIS
# -----------------------------------------------------------------------------
def analyze_subreddit(subreddit_name: str = "CryptoCurrency", limit: int = 100, run_id: str = ""):
    posts = fetch_reddit_posts(subreddit_name, limit)

    if posts is None or len(posts) == 0:
        return pd.DataFrame(), pd.DataFrame()

    raw_rows = []
    summary_metrics = {"BTC": [], "ETH": [], "GENERAL": []}
    seen_hashes = set()
    subreddit_weight = SUBREDDIT_WEIGHTS.get(subreddit_name, 1.0)

    now = datetime.utcnow()
    year, month, day = now.strftime("%Y"), now.strftime("%m"), now.strftime("%d")

    for post in posts:
        try:
            pdata = post["data"]
            if pdata.get("stickied"):
                continue

            title = pdata.get("title", "") or ""
            body = pdata.get("selftext", "") or ""
            if body in ["[removed]", "[deleted]"]:
                continue

            full_text = f"{title}. {body}".strip()
            if len(full_text) < 20:
                continue

            lang = safe_detect_language(full_text)
            if lang != "en":
                continue

            content_hash = generate_content_hash(full_text)
            if content_hash in seen_hashes:
                continue
            seen_hashes.add(content_hash)

            asset = detect_asset(full_text)
            event_tags = extract_event_tags(full_text)

            sentiment = analyzer.polarity_scores(full_text)
            compound_score = sentiment["compound"]

            upvotes = int(pdata.get("score", 0) or 0)
            comments = int(pdata.get("num_comments", 0) or 0)
            created_ts = float(pdata.get("created_utc") or datetime.now(timezone.utc).timestamp())
            created_dt = datetime.fromtimestamp(created_ts, tz=timezone.utc)

            hours_old = max((datetime.now(timezone.utc) - created_dt).total_seconds() / 3600, 1)
            time_decay = calculate_time_decay(created_dt)
            engagement_velocity = (upvotes + comments) / hours_old
            interaction_weight = (upvotes * 1.0) + (comments * 3.0)
            final_weight = interaction_weight * time_decay * subreddit_weight
            weighted_sentiment = compound_score * final_weight

            permalink = pdata.get("permalink", "") or ""
            reddit_url = permalink if permalink.startswith("http") else f"https://reddit.com{permalink}"
            is_viral = engagement_velocity > 100

            raw_rows.append(
                {
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
                    "source": "reddit_rss_scraping",
                    "run_id": run_id,
                    "ingestion_time": now,
                    "year": year,
                    "month": month,
                    "day": day,
                }
            )

            summary_metrics[asset].append(
                {
                    "sentiment": compound_score,
                    "weighted_sentiment": weighted_sentiment,
                    "interaction_weight": interaction_weight,
                    "is_viral": is_viral,
                    "event_tags": event_tags,
                }
            )

        except Exception as exc:
            logging.error(f"❌ Analysis Error: {exc}", exc_info=True)

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

        summary_rows.append(
            {
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
                "source": "reddit_rss_batch_pipeline",
                "run_id": run_id,
                "ingestion_time": now,
                "year": year,
                "month": month,
                "day": day,
            }
        )

    raw_df = pd.DataFrame(raw_rows)
    summary_df = pd.DataFrame(summary_rows)
    logging.info(f"✅ [{subreddit_name}] RAW={len(raw_df)} | SUMMARY={len(summary_df)}")
    return raw_df, summary_df


# -----------------------------------------------------------------------------
# ENTRYPOINT
# -----------------------------------------------------------------------------
def main() -> None:
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
        if not raw_df.empty:
            all_raw.append(raw_df)
        if not summary_df.empty:
            all_summary.append(summary_df)
        time.sleep(random.uniform(3, 6))

    if not all_raw:
        logging.error("❌ No Reddit data collected.")
        raise RuntimeError("No Reddit data collected. Failing the job to prevent partial uploads.")

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
        save_dataframe_to_parquet(
            raw_final,
            raw_output_dir,
            file_prefix="reddit_raw",
            partition_cols=["subreddit", "asset", "year", "month", "day"],
        )
        save_dataframe_to_parquet(
            summary_final,
            summary_output_dir,
            file_prefix="reddit_summary",
            partition_cols=["subreddit", "asset", "year", "month", "day"],
        )

    print("\n📊 REDDIT FEATURE SUMMARY")
    print(summary_final.to_string())

    print("\n🔥 TOP VIRAL POSTS")
    top_viral = raw_final.sort_values(by="engagement_velocity", ascending=False).head(5)
    for _, row in top_viral.iterrows():
        print(
            f"\n[{row['asset']}] "
            f"Velocity={row['engagement_velocity']} "
            f"| Sentiment={row['sentiment_compound']}"
        )
        print(str(row["title"])[:200])


if __name__ == "__main__":
    main()
