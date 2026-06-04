import os
import time
import sys
import json
import logging
import yaml
from web3 import Web3
from kafka import KafkaProducer
from dotenv import load_dotenv

current_dir = os.path.dirname(os.path.abspath(__file__))

logic_dir = os.path.join(os.path.dirname(current_dir), "logic_crypto_streaming")

if logic_dir not in sys.path:
    sys.path.insert(0, logic_dir)

import utils.config_parser as config_parser

# Load environment variables from .env file
load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class MultiCoinWhaleHunter:
    def __init__(self, config_path="configs/trading_params.yaml"):

        # 1. SECURITY: Fetch URL and Broker from environment variables
        self.alchemy_url = os.getenv("ALCHEMY_WSS_URL") # API key from Alchemy
        self.broker = os.getenv("KAFKA_BROKER", "localhost:19092") # Set up in redpanda
        
        # Check if Alchemy URL is set
        if not self.alchemy_url:
            raise ValueError("🔥 ERROR: ALCHEMY_WSS_URL not found in .env file!")

        # 2. CONNECT TO BLOCKCHAIN: Connect to Web3 via Alchemy
        self.w3 = Web3(Web3.LegacyWebSocketProvider(self.alchemy_url))

        # 3. CONNECT TO KAFKA: Connect to Kafka via Kafka-Python  
        self.producer = KafkaProducer(
            bootstrap_servers=[self.broker],
            value_serializer=lambda x: json.dumps(x).encode('utf-8') # Transform to JSON and bytes for Kafka
        )
        self.topic = "crypto_onchain_alerts" # Set up topic in Kafka
        
        # 4. DYNAMIC THRESHOLDS: Read from YAML file
        self.config = self._load_config(config_path)
        onchain_params = self.config.get('onchain_filters', {})
        
        # Map Contract addresses to flexible configurations from YAML
        self.TARGET_ADDRESS = {
            self.w3.to_checksum_address('0xdAC17F958D2ee523a2206206994597C13D831ec7'): onchain_params.get('USDT', {}), # USDT
            self.w3.to_checksum_address("0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599"): onchain_params.get('WBTC', {}), # WBTC
            self.w3.to_checksum_address("0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"): onchain_params.get('WETH', {})  # WETH
        }

        # 5. QUANT LOGIC: EXCHANGE HOT WALLETS (e.g., Known Binance wallets)
        self.KNOWN_EXCHANGES = [
            self.w3.to_checksum_address("0x28C6c06299d547675E1dB752Fec124D6Fa0D8408"), # Binance 14
            self.w3.to_checksum_address("0xF977814e90dA44bFA03b6295A0616a897441aceC"), # Binance 8
            self.w3.to_checksum_address("0xdfd5293d8e347dfe59e90efd55b2956a1343963d"), # Binance 15
        ]

        # Configure ABI for ERC-20 Transfer event
        self.transfer_abi = [
            {
                "anonymous": False,
                "inputs": [
                    {"indexed": True, "internalType": "address", "name": "from", "type": "address"},  # From address
                    {"indexed": True, "internalType": "address", "name": "to", "type": "address"},    # To address
                    {"indexed": False, "internalType": "uint256", "name": "value", "type": "uint256"} # Amount
                ],
                "name": "Transfer",
                "type": "event"
            }
        ]
        
        # Set up generic contract for ERC-20 Transfer event
        self.generic_contract = self.w3.eth.contract(abi=self.transfer_abi)

    # 6. Load configuration from YAML for dynamic thresholds
    def _load_config(self, file_path):
        """Load configuration from YAML for dynamic thresholds"""
        try:
            return config_parser.load_config(file_path)
        except Exception as e:
            logging.error(f"Failed to read config file: {e}")
            return {}

    # 7. Handle WebSocket disconnections and reconnects
    def connect(self):
        """Handle WebSocket disconnections and reconnects"""
        self.w3 = Web3(Web3.LegacyWebSocketProvider(self.alchemy_url))
        if self.w3.is_connected():
            logging.info("🟢 Successfully connected to Blockchain via Alchemy!")
            return True
        return False

    # 8. Start the main loop
    def start(self):
        # Outer loop for auto-reconnection
        while True:
            try:
                if not self.connect(): # Reconnect if disconnected
                    time.sleep(5)
                    continue

                contract_addresses = list(self.TARGET_ADDRESS.keys()) # List of contract addresses
                transfer_topic_hash = self.w3.keccak(text="Transfer(address,address,uint256)").hex() # Transfer event signature hash

                # Filter for Transfer events
                multi_filter = self.w3.eth.filter({
                    "address": contract_addresses,
                    "topics": [transfer_topic_hash]
                })
                
                logging.info("🔥 Casting the net for Whales (Dynamic Threshold)...")

                # Inner loop for real-time data extraction
                while True:
                    # Get new Transfer events
                    new_logs = multi_filter.get_new_entries()
                    for log in new_logs:
                        # Get token info from TARGET_ADDRESS map
                        token_info = self.TARGET_ADDRESS.get(log.address) 

                        # Skip if token is not in the TARGET_ADDRESS map
                        if not token_info:
                            continue
                        
                        # Parse Transfer event
                        event = self.generic_contract.events.Transfer().process_log(log)
                        
                        from_addr = event['args']['from'] # get from address
                        to_addr = event['args']['to'] # get to address
                        raw_amount = event['args']['value'] # get amount
                        
                        # Convert decimal places based on token spec
                        decimals = token_info.get("decimals", 18)
                        real_amount = raw_amount / (10 ** decimals) # convert to float
                        
                        # LOGIC: Filter out noise (dust transactions) based on YAML config
                        min_base = token_info.get("min_base_transfer", 0)
                        
                        # Check to address for known exchanges
                        if real_amount >= min_base:
                            is_inflow = to_addr in self.KNOWN_EXCHANGES
                            is_outflow = from_addr in self.KNOWN_EXCHANGES

                            if is_inflow:
                                tx_type = "INFLOW"
                            elif is_outflow:
                                tx_type = "OUTFLOW"
                            else:
                                tx_type = "WALLET_TO_WALLET"
                            
                            symbol = "USDT" if decimals == 6 else ("WBTC" if decimals == 8 else "WETH")
                            
                            payload = {
                                'blockchain': 'Ethereum',
                                'symbol': symbol,
                                'amount': real_amount,
                                'from_address': from_addr,
                                'to_address': to_addr,
                                'tx_type': tx_type,
                                'tx_hash': log.transactionHash.hex(),
                                'timestamp': int(time.time())
                            }
                            
                            self.producer.send(self.topic, payload)
                            
                            if tx_type == "INFLOW":
                                logging.warning(f"🚨 BEARISH: {real_amount:,.0f} {symbol} JUST DEPOSITED TO EXCHANGE! (Prepare for dump)")
                            elif tx_type == "OUTFLOW":
                                logging.info(f"🚀 BULLISH: {real_amount:,.0f} {symbol} WITHDRAWN FROM EXCHANGE! (Supply shock)")
                            else:
                                logging.info(f"🐳 NEUTRAL: {real_amount:,.0f} {symbol} transferred between private wallets.")
                    
                    time.sleep(2) # Sleep for 2 seconds reduces load on the blockchain
                    
            except Exception as e:
                logging.error(f"❌ Connection lost: {e}. Retrying in 5s...")
                time.sleep(5) # Sleep for 5 seconds to avoid spamming the blockchain
                
            except KeyboardInterrupt:
                logging.info("🛑 Shutting down gracefully...")
                break
                
        if self.producer:
            self.producer.flush()
            self.producer.close()

if __name__ == "__main__":
    yaml_path = os.path.join(logic_dir, "configs", "trading_params.yaml")
    
    hunter = MultiCoinWhaleHunter(config_path=yaml_path)

    hunter.start()
