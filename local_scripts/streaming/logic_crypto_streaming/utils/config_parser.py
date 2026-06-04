import yaml
import os
import logging

def load_config(file_path="configs/trading_params.yaml"):
    """
    Loads the YAML configuration file dynamically.
    Ensures that path is relative to the project root.
    Provides a dictionary containing all Quant parameters for Flink SQL.
    """
    if not os.path.exists(file_path):
        logging.error(f"❌ CRITICAL: Configuration file not found at: {file_path}")
        raise FileNotFoundError(f"Configuration file not found at: {file_path}")
        
    with open(file_path, "r", encoding="utf-8") as file:
        config_data = yaml.safe_load(file)
        logging.info(f"✅ Successfully loaded Quant Trading Parameters from {file_path}")
        return config_data