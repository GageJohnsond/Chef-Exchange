"""
User management module for Stock Exchange Discord Bot
Handles user data, balances, and inventory
"""
import logging
from typing import Dict, Union

import config
from data_manager import DataManager

logger = logging.getLogger('stock_exchange.user')

class UserManager:
    """Class to handle user-related operations"""
    
    @staticmethod
    def get_balance(user_id: Union[int, str]) -> float:
        """Get the balance of a user"""
        data = DataManager.load_data(config.USER_DATA_FILE)
        return data[str(user_id)].get("balance", 100)
    
    @staticmethod
    def update_balance(user_id: Union[int, str], amount: float) -> None:
        """Update the balance of a user"""
        data = DataManager.load_data(config.USER_DATA_FILE)
        data[str(user_id)]["balance"] += amount
        DataManager.save_data(config.USER_DATA_FILE, data)
        logger.debug(f"Updated balance for user {user_id} by {amount}")
    
    @staticmethod
    def get_bank(user_id: Union[int, str]) -> float:
        """Get the bank balance of a user"""
        data = DataManager.load_data(config.USER_DATA_FILE)
        return data[str(user_id)]["bank"]
    
    @staticmethod
    def deposit(user_id: Union[int, str], amount: float) -> bool:
        """Deposit amount from balance to bank"""
        data = DataManager.load_data(config.USER_DATA_FILE)
        uid = str(user_id)
        
        if data[uid]["balance"] >= amount:
            data[uid]["balance"] -= amount
            data[uid]["bank"] += amount
            DataManager.save_data(config.USER_DATA_FILE, data)
            logger.info(f"User {uid} deposited {amount} to bank")
            return True
        
        logger.debug(f"User {uid} failed to deposit {amount} (insufficient funds)")
        return False
    
    @staticmethod
    def withdraw(user_id: Union[int, str], amount: float) -> bool:
        """Withdraw amount from bank to balance"""
        data = DataManager.load_data(config.USER_DATA_FILE)
        uid = str(user_id)
        
        if data[uid]["bank"] >= amount:
            data[uid]["bank"] -= amount
            data[uid]["balance"] += amount
            DataManager.save_data(config.USER_DATA_FILE, data)
            logger.info(f"User {uid} withdrew {amount} from bank")
            return True
        
        logger.debug(f"User {uid} failed to withdraw {amount} (insufficient funds)")
        return False
    
    @staticmethod
    def user_inventory(user_id: Union[int, str]) -> Dict[str, int]:
        """Get the inventory of a user"""
        data = DataManager.load_data(config.USER_DATA_FILE)
        return data[str(user_id)]["inventory"]
    
    @staticmethod
    def add_item(user_id: Union[int, str], item: str) -> None:
        """Add an item to a user's inventory"""
        data = DataManager.load_data(config.USER_DATA_FILE)
        uid = str(user_id)
        inv = data[uid]["inventory"]
        
        if item in inv:
            inv[item] += 1
        else:
            inv[item] = 1
        
        DataManager.save_data(config.USER_DATA_FILE, data)
        logger.info(f"Added {item} to user {uid}'s inventory")
    
    @staticmethod
    def remove_item(user_id: Union[int, str], item: str) -> None:
        """Remove an item from a user's inventory"""
        data = DataManager.load_data(config.USER_DATA_FILE)
        uid = str(user_id)
        inv = data[uid]["inventory"]
        
        if item in inv:
            if inv[item] > 1:
                inv[item] -= 1
                logger.info(f"Decreased {item} quantity for user {uid}")
            else:
                del inv[item]
                logger.info(f"Removed {item} from user {uid}'s inventory")
            
            DataManager.save_data(config.USER_DATA_FILE, data)