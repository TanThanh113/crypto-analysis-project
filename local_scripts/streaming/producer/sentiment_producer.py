import os
import json
import logging
import time
import requests
from kafka import KafkaProducer
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Create a class to manage sentiment producer
class SentimentHunter:
    def __init__(self, broker=None):
        # 1. CONFIGURATION & SECURITY
        self.broker = broker or os.getenv("KAFKA_BROKER", "localhost:19092")
        self.topic = "crypto_sentiment" # Set up topic in Kafka (manage data sentiment)
        
        # 2. STATE MANAGEMENT (To calculate Deltas)
        self.previous_oi = {}
        
        # 3. HTTP SESSION OPTIMIZATION
        # (An improved method, instead of using the traditional GET method, would be much more time-consuming.)
        self.session = requests.Session()

        # 4. CONNECT TO KAFKA
        try:
            self.producer = KafkaProducer(
                bootstrap_servers=[self.broker],
                value_serializer=lambda v: json.dumps(v).encode('utf-8'),
                linger_ms=10
            )
            logging.info("✅ Kafka connected for Sentiment Stream!")
        except Exception as e:
            logging.critical(f"🔥 Kafka connection failed: {e}")
            exit(1)
    def fetch_sentiment_data(self, symbol="BTCUSDT"):
        """
        Fetches Long/Short Ratio, Open Interest, and Funding Rate.
        Calculates OI Delta to detect sudden position building.
        """
        try:
            # Endpoint 1: Global Long/Short Ratio (Accounts)
            ls_url = "https://fapi.binance.com/futures/data/globalLongShortAccountRatio"

            # Structure when retrieving data
            ls_params = {'symbol': symbol, 'period': '5m', 'limit': 1}
            ls_response = self.session.get(ls_url, params=ls_params, timeout=5).json()
            
            # Logic check for response
            if not ls_response or 'longShortRatio' not in ls_response[0]:
                return
            
            data = ls_response[0]
            long_ratio = float(data['longAccount']) * 100 # Convert to %
            short_ratio = float(data['shortAccount']) * 100 # Convert to %
            
            # Endpoint 2: Open Interest (Total money on the table)
            oi_url = "https://fapi.binance.com/fapi/v1/openInterest"
            oi_params = {'symbol': symbol}
            oi_response = self.session.get(oi_url, params=oi_params, timeout=5).json()
            open_interest = float(oi_response.get('openInterest', 0))
            
            # Endpoint 3: Funding Rate (The cost of leverage)
            fr_url = "https://fapi.binance.com/fapi/v1/premiumIndex"
            fr_response = self.session.get(fr_url, params={'symbol': symbol}, timeout=5).json()
            funding_rate = float(fr_response.get('lastFundingRate', 0)) * 100  # Convert to %
            
            # Calculate OI Delta (Momentum)
            prev_oi = self.previous_oi.get(symbol, open_interest)
            oi_delta_pct = ((open_interest - prev_oi) / prev_oi * 100) if prev_oi > 0 else 0.0
            self.previous_oi[symbol] = open_interest # Update state
            
            # 4. Pack and Send Payload
            payload = {
                'symbol': symbol,
                'long_percent': round(long_ratio, 2),
                'short_percent': round(short_ratio, 2),
                'open_interest': open_interest,
                'oi_delta_pct': round(oi_delta_pct, 3), # Crucial for Quant models
                'funding_rate_pct': round(funding_rate, 4), # Crucial for Quant models
                'timestamp': int(time.time())
            }
            
            self.producer.send(self.topic, payload)
            
            # Detailed Logging
            logging.info(f"🧠 SENTIMENT [{symbol}]: L/S: {payload['long_percent']}%/{payload['short_percent']}% "
                         f"| FR: {payload['funding_rate_pct']}% | OI Delta: {payload['oi_delta_pct']}%")
            
            # Tactical Alerts
            if payload['long_percent'] > 70 and payload['funding_rate_pct'] > 0.05:
                logging.warning(f"⚠️ LIQUIDATION THREAT [{symbol}]: Heavy Long bias + High Funding. Dump imminent!")
            elif payload['oi_delta_pct'] > 2.0:
                logging.warning(f"🐳 VOLATILITY ALERT [{symbol}]: Open Interest spiked by {payload['oi_delta_pct']}%. Big move loading!")

        except requests.exceptions.RequestException as e:
            logging.error(f"❌ Network/API Error fetching Sentiment: {e}")
        except Exception as e:
            logging.error(f"❌ Unexpected Error: {e}")

    def fetch_macro_sentiment(self):
        """
        Macro data pull (Updated only every few hours).
        Source: Alternative.me (F&G) and CoinGecko (BTC Dominance).
        """
        try:
            # 1. Scroll down the Fear & Greed Index (F&G) website
            fng_url = "https://api.alternative.me/fng/?limit=1"
            fng_response = self.session.get(fng_url, timeout=5).json()
            fng_value = int(fng_response['data'][0]['value'])
            fng_classification = fng_response['data'][0]['value_classification']
            
            # 2. Use Global Market Data (CoinGecko) to get BTC Dominance.
            # Note: CoinGecko limits requests to 10-30 per minute (Please keep your calls to a minimum).
            cg_url = "https://api.coingecko.com/api/v3/global"
            cg_response = self.session.get(cg_url, timeout=5).json()
            btc_dominance = cg_response['data']['market_cap_percentage']['btc']

            payload = {
                'symbol': 'GLOBAL_MACRO', # Mark this as global macroeconomic data.
                'fear_greed_index': fng_value,
                'fear_greed_label': fng_classification,
                'btc_dominance_pct': round(btc_dominance, 2),
                'timestamp': int(time.time())
            }

            # When you shoot into the same topic, Flink/BigQuery will identify it using the symbol 'GLOBAL_MACRO'.
            self.producer.send("crypto_macro", payload)
            
            logging.info(f"🌍 GLOBAL_MACRO: Fear & Greed: {fng_value} ({fng_classification}) | BTC Dominance: {payload['btc_dominance_pct']}%")

        except Exception as e:
            logging.error(f"❌ Error data GLOBAL_MACRO (F&G/BTC.D): {e}")

    def start(self):
        logging.info("🚀 Starting Macro Sentiment & Liquidity Radar...")

        loop_counter = 0
        
        try:
            while True:
                self.fetch_sentiment_data("BTCUSDT")
                self.fetch_sentiment_data("ETHUSDT")
                
                if loop_counter % 12 == 0:
                    self.fetch_macro_sentiment()
                
                loop_counter += 1

                # Sleep for 5 minutes (Binance Long/Short API minimum timeframe)
                time.sleep(300)
                
        except KeyboardInterrupt:
            logging.info("🛑 Shutting down Sentiment Radar...")
        finally:
            if self.producer:
                self.producer.flush()
                self.producer.close()
                logging.info("✅ Kafka Producer closed safely.")

if __name__ == "__main__":
    hunter = SentimentHunter()
    hunter.start()
