import json
import os.path
import pandas as pd

def load_configuration():
    """Load and return configuration from JSON file."""
    with open('config/config.json', 'r', encoding='utf-8') as file:
        return json.load(file)

def initialize_components(config):
    """Initialize and return all application components."""
    
    # Initialize logger first since other components need it
    
    from utils.logger import setup_logger
    
    logger = setup_logger(name="trading_bot_logger", level=logging.INFO)
    
    # Initialize trading components
    
    from modules.trader import Trader
    
     trader = Trader(
        api_key=config["LBANK"]["api_key"],
        secret_key=config["LBANK"]["api_secret"]
     )
     
     # Initialize other components...
     
     return {
         'logger': logger,
         'trader': trader,
         'websocket_client': WebSocketClient(
             symbols=config["SYMBOLS"],
             timeframes=config["TIMEFRAMES"]
         ),
         # ... other components ...
     }
