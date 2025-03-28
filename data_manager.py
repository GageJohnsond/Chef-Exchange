"""
Data management module for Stock Exchange Discord Bot
Handles loading and saving data from JSON files
"""
import os
import json
import logging
from typing import Dict, Any, Union

import config

logger = logging.getLogger('stock_exchange.data')

class DataManager:
    """Class to handle all data loading and saving operations"""
    
    @staticmethod
    def ensure_files_exist() -> None:
        """Ensure all required data files exist"""
        # Check for user data file
        if not os.path.exists(config.USER_DATA_FILE):
            with open(config.USER_DATA_FILE, "w") as f:
                json.dump({}, f)
            logger.info(f"Created empty {config.USER_DATA_FILE}")
            
        # Check for stocks data file
        if not os.path.exists(config.STOCKS_FILE):
            with open(config.STOCKS_FILE, "w") as f:
                json.dump({
                    "STOCK_PRICES": {},
                    "PRICE_HISTORY": {},
                    "STOCK_SYMBOLS": {},
                    "USER_TO_TICKER": {}
                }, f)
            logger.info(f"Created empty {config.STOCKS_FILE} with initial data")
            
        # Check for stock messages file
        if not os.path.exists(config.STOCK_MESSAGES_FILE):
            with open(config.STOCK_MESSAGES_FILE, "w") as f:
                json.dump({}, f)
            logger.info(f"Created empty {config.STOCK_MESSAGES_FILE}")

    
    @staticmethod
    def load_data(filename: str) -> Dict:
        """Load data from a JSON file"""
        try:
            with open(filename, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError) as e:
            logger.error(f"Error loading {filename}: {e}")
            return {}
    
    @staticmethod
    def save_data(filename: str, data: Dict) -> None:
        """Save data to a JSON file"""
        try:
            with open(filename, "w") as f:
                json.dump(data, f, indent=0)
            logger.debug(f"Data saved to {filename}")
        except Exception as e:
            logger.error(f"Error saving to {filename}: {e}")
    
    @staticmethod
    def ensure_user(user_id: Union[int, str]) -> Dict:
        """Ensure a user exists in the data and return the updated data"""
        data = DataManager.load_data(config.USER_DATA_FILE)
        uid = str(user_id)
        
        if uid not in data:
            data[uid] = config.DEFAULT_USER_DATA.copy()
            DataManager.save_data(config.USER_DATA_FILE, data)
            logger.info(f"Created new user data for {uid}")
        
        return data