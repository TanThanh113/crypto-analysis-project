import json
import logging
import time
import threading
import websocket
from kafka import KafkaProducer
from kafka.admin import KafkaAdminClient, NewTopic
from kafka.errors import TopicAlreadyExistsError
from dotenv import load_dotenv
import os
import requests

# Load environment variables from .env file
load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class BinanceFullStreamer:
    def __init__(self, broker=None, symbols=None, num_partitions=4):
        
        # 1. ĐỌC TRỰC TIẾP TỪ FILE .ENV CỦA BẠN
        if broker is None:
            self.broker = os.getenv("KAFKA_BROKER", "localhost:19092")
        else:
            self.broker = broker
            
        logging.info(f"🎯 Target Kafka Broker set to: {self.broker}")

        self.symbols = [s.lower() for s in (symbols if symbols else ["btcusdt", "ethusdt"])]
        self.num_partitions = num_partitions

        # Create three topics for each symbol
        self.topics = {
            'trade' : 'crypto_trades',
            'book': 'crypto_orderbook',
            'liquidation': 'crypto_liquidations'
        }

        # Create URLs for the Spot Market (Including Trade and OrderBook)
        spot_streams = [f"{s}@trade" for s in self.symbols] + [f"{s}@depth20@100ms" for s in self.symbols]
        self.spot_ws_url = f"wss://stream.binance.com:9443/stream?streams={'/'.join(spot_streams)}"

        # Create URLs for the Futures Market (Including ForceOrder)
        futures_streams = [f"{s}@forceOrder" for s in self.symbols]
        self.futures_ws_url = f"wss://fstream.binance.com/ws/{'/'.join(futures_streams)}"
        
        self.last_trade_id = {}

        self.last_alert_time = {}
        self._setup_topic()
        self.producer = self._init_producer()

    def _setup_topic(self):
        """This function automatically checks and creates a topic with 4 partitions."""
        logging.info(f"🛠️ Checking 3 Topics with {self.num_partitions} partitions...")
        admin_client = None
        try:
            admin_client = KafkaAdminClient(bootstrap_servers=self.broker)

            for topic in self.topics.values():
                try: 
                    new_topic = NewTopic(name=topic, num_partitions=self.num_partitions, replication_factor=1)
                    admin_client.create_topics(new_topics=[new_topic], validate_only=False)
                    logging.info(f"✅ Created Topic '{topic}' with {self.num_partitions} Partitions!")
                except TopicAlreadyExistsError:
                    pass

        except Exception as e:
            logging.error(f"❌ Error when creating Topic: {e}")
        finally:
            if admin_client:
                admin_client.close()

    def _init_producer(self):
        """Create Kafka Producer in an automated way."""
        logging.info(f"⏳ Creating Kafka Producer connecting to: {self.broker}...")
        try:
            producer = KafkaProducer(
                bootstrap_servers=self.broker, 
                value_serializer=lambda v: json.dumps(v).encode('utf-8'),
                compression_type='gzip',
                linger_ms=10
            )
            logging.info("✅ Created Kafka Producer successfully!")
            return producer
        except Exception as e:
            logging.critical(f"🔥 CRITICAL ERROR: Unable to connect to Kafka/Redpanda: {e}")
            exit(1)

    def on_message(self, ws, message):
        """Data classification (Routing) to throw it into the right topic"""
        try:
            raw_payload = json.loads(message)
            if 'stream' not in raw_payload:
                return
                
            stream_name = raw_payload['stream']
            data = raw_payload['data']
            symbol = stream_name.split('@')[0].upper()
            
            if '@trade' in stream_name:
                trade_id = data['t']
                last_id = self.last_trade_id.get(symbol)
                
                if last_id is not None:
                    expected = last_id + 1
                    if trade_id > expected:
                        missing_count = trade_id - expected
                        logging.warning(f"⚠️ [GAP DETECTED] {symbol}: Missing {missing_count} transactions.")
                        
                self.last_trade_id[symbol] = trade_id       
                payload = {
                    'symbol': symbol,
                    'trade_id': data['t'],
                    'price': float(data['p']),
                    'quantity': float(data['q']),
                    'event_time': data['E'],
                    'trade_time': data['T']
                }
                self.producer.send(self.topics['trade'], payload)

            elif '@depth20' in stream_name:
                bids = data['bids']
                asks = data['asks']
                
                if not bids or not asks:
                    return
                    
                best_bid = float(bids[0][0])
                best_ask = float(asks[0][0])
                
                bid_vol_1pct = sum(float(p) * float(q) for p, q in bids if float(p) >= best_bid * 0.99)
                ask_vol_1pct = sum(float(p) * float(q) for p, q in asks if float(p) <= best_ask * 1.01)
                
                imbalance_ratio = (ask_vol_1pct / bid_vol_1pct) if bid_vol_1pct > 0 else 999.0
                
                payload = {
                    'symbol': symbol,
                    'best_bid_price': best_bid,
                    'best_ask_price': best_ask,
                    'bid_vol_1pct_usd': bid_vol_1pct,
                    'ask_vol_1pct_usd': ask_vol_1pct,
                    'imbalance_ratio': round(imbalance_ratio, 2),
                    'event_time': int(time.time() * 1000) 
                }
                self.producer.send(self.topics['book'], payload)

                current_time = time.time()
                last_alert = self.last_alert_time.get(symbol, 0)
                
                if imbalance_ratio > 10.0 and (current_time - last_alert) > 60:
                    logging.warning(f"🧱 MASSIVE SELL WALL [{symbol}]: {imbalance_ratio:.1f}x higher! (Next alert in 60s)")
                    self.last_alert_time[symbol] = current_time

            elif '@forceOrder' in stream_name:
                order = data['o']
                payload = {
                    'symbol': order['s'],
                    'side': order['S'], 
                    'price': float(order['p']),
                    'quantity': float(order['q']),
                    'event_time': data['E']
                }
                self.producer.send(self.topics['liquidation'], payload)
                logging.error(f"🔥 LIQUIDATION: {payload['symbol']} - Order {payload['side']} burned {payload['quantity']} coins at price {payload['price']}")
        
        except Exception as e:
            logging.error(f"Error when processing message: {e}")

    def on_error(self, ws, error):
        logging.error(f"WebSocket error: {error}")

    def on_close(self, ws, close_status_code, close_msg):
        logging.warning("🔴 Disconnected from Binance WebSocket.")

    def on_open(self, ws):
        logging.info(f"🟢 Connected to Binance for pairs: {self.symbols}")

    def _run_websocket(self, url, name):
        """Function to run a websocket connection"""
        while True:
            try:
                logging.info(f"Setting up {name} WebSocket connection...")
                ws = websocket.WebSocketApp(
                    url, 
                    on_open=self.on_open,
                    on_message=self.on_message,
                    on_error=self.on_error,
                    on_close=self.on_close
                )
                ws.run_forever(ping_interval=60, ping_timeout=10)
                logging.warning(f"{name} WebSocket disconnected. Retrying in 5 seconds...")
                time.sleep(5)
            except Exception as e:
                logging.error(f"{name} error: {e}. Retrying in 5 seconds...")
                time.sleep(5)

    def stop(self):
        logging.info("⏳ Streamer paused and resources cleaned up...")
        if self.producer:
            self.producer.flush()
            self.producer.close()
            logging.info("Kafka Producer closed.")

    def start(self):
        t_spot = threading.Thread(target=self._run_websocket, args=(self.spot_ws_url, "SPOT"), daemon=True)
        t_futures = threading.Thread(target=self._run_websocket, args=(self.futures_ws_url, "FUTURES"), daemon=True)

        t_spot.start()
        t_futures.start() 

        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logging.info("Shutting down streamer...")
        finally:
            self.stop()

if __name__ == "__main__":
    
    symbols = ["btcusdt", "ethusdt"]
    streamer = BinanceFullStreamer(broker=None, symbols=symbols)
    streamer.start()
