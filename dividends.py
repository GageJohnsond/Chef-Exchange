"""
Dividend system for Stock Exchange Discord Bot
Handles dividend payments to top shareholders and stock creators
"""
import logging
import random
from datetime import datetime
import pytz
from typing import Dict, List, Tuple

import config
from data_manager import DataManager
from user_manager import UserManager
from stock_manager import StockManager

logger = logging.getLogger('stock_exchange.dividends')

class DividendManager:
    """Class to handle all dividend payment operations"""
    
    # Constants for dividend calculations
    TOP_SHAREHOLDERS_COUNT = 3  # Number of top shareholders to reward
    
    # Dividend percentages (of stock price)
    CREATOR_DIVIDEND_PERCENT = 0.5  # 0.5% of stock price per shareholder
    
    # Top shareholder percentages (of stock price)
    TOP_SHAREHOLDER_DIVIDENDS = {
        0: 1.0,  # 1% of stock price to top shareholder
        1: 0.5,  # 0.5% of stock price to second place
        2: 0.25  # 0.25% of stock price to third place
    }

    @classmethod
    def process_dividends(cls) -> Dict[str, float]:
        """
        Process all dividend payments.
        
        Returns:
            Dictionary mapping user IDs to dividend amounts
        """
        # Load all user data
        user_data = DataManager.load_data(config.USER_DATA_FILE)
        
        # Track dividends for each user
        dividends = {}
        
        # Process each stock
        for symbol in StockManager.get_all_symbols():
            if symbol not in StockManager.stock_prices:
                continue
                
            # Get current stock price
            stock_price = StockManager.stock_prices[symbol]
            
            # Skip stocks with zero or negative price (shouldn't happen normally)
            if stock_price <= 0:
                continue
                
            # 1. Find all shareholders and their holdings
            shareholders = cls._get_shareholders(user_data, symbol)
            
            # 2. Pay dividends to top shareholders
            cls._pay_top_shareholder_dividends(symbol, stock_price, shareholders, dividends)
            
            # 3. Pay dividends to stock creator
            cls._pay_creator_dividends(symbol, stock_price, shareholders, dividends)
        
        # Apply all dividends to user balances
        cls._apply_dividends(dividends)
        
        return dividends
    
    @classmethod
    def _get_shareholders(cls, user_data: Dict, symbol: str) -> List[Tuple[str, int]]:
        """
        Get all shareholders of a stock and their holdings.
        
        Args:
            user_data: Dictionary of all user data
            symbol: Stock symbol to check
            
        Returns:
            List of (user_id, shares) tuples sorted by shares (descending)
        """
        shareholders = []
        
        for user_id, data in user_data.items():
            inventory = data.get("inventory", {})
            
            if symbol in inventory and inventory[symbol] > 0:
                shareholders.append((user_id, inventory[symbol]))
        
        # Sort by number of shares (descending)
        shareholders.sort(key=lambda x: x[1], reverse=True)
        return shareholders
    
    @classmethod
    def _pay_top_shareholder_dividends(cls, symbol: str, stock_price: float, 
                                      shareholders: List[Tuple[str, int]], dividends: Dict[str, float]) -> None:
        """
        Calculate and track dividends for top shareholders.
        
        Args:
            symbol: Stock symbol
            stock_price: Current stock price
            shareholders: List of (user_id, shares) tuples sorted by shares
            dividends: Dictionary tracking dividend amounts by user
        """
        # Pay dividends to top shareholders (if any)
        for rank, (user_id, shares) in enumerate(shareholders[:cls.TOP_SHAREHOLDERS_COUNT]):
            if rank in cls.TOP_SHAREHOLDER_DIVIDENDS:
                # Calculate dividend based on rank and stock price
                percent = cls.TOP_SHAREHOLDER_DIVIDENDS[rank]
                dividend_amount = round(stock_price * (percent / 100), 2)
                
                # Add to user's dividend total
                if user_id not in dividends:
                    dividends[user_id] = 0
                dividends[user_id] += dividend_amount
                
                logger.debug(f"Top shareholder dividend: {user_id} received ${dividend_amount} from {symbol} (rank {rank+1})")

    @classmethod
    def _pay_creator_dividends(cls, symbol: str, stock_price: float, 
                               shareholders: List[Tuple[str, int]], dividends: Dict[str, float]) -> None:
        """
        Calculate and track dividends for stock creator based on other shareholders.
        
        Args:
            symbol: Stock symbol
            stock_price: Current stock price
            shareholders: List of (user_id, shares) tuples
            dividends: Dictionary tracking dividend amounts by user
        """
        # Find creator of this stock
        creator_id = None
        for user_id, ticker in StockManager.user_to_ticker.items():
            if ticker == symbol:
                creator_id = user_id
                break
        
        if not creator_id:
            return  # No creator found for this stock
        
        # Count shares held by other users (excluding creator)
        total_other_shares = 0
        for user_id, shares in shareholders:
            if user_id != creator_id:
                total_other_shares += shares
        
        # Calculate creator dividend based on other holders
        if total_other_shares > 0:
            # Base dividend on stock price and number of shares others hold
            dividend_amount = round(stock_price * (cls.CREATOR_DIVIDEND_PERCENT / 100) * total_other_shares, 2)
            
            # Add to creator's dividend total
            if creator_id not in dividends:
                dividends[creator_id] = 0
            dividends[creator_id] += dividend_amount
            
            logger.debug(f"Creator dividend: {creator_id} received ${dividend_amount} from {symbol} ({total_other_shares} shares held by others)")
    
    @classmethod
    def _apply_dividends(cls, dividends: Dict[str, float]) -> None:
        """
        Apply calculated dividends to user balances.
        
        Args:
            dividends: Dictionary mapping user IDs to dividend amounts
        """
        for user_id, amount in dividends.items():
            if amount > 0:
                UserManager.update_balance(user_id, amount)
                logger.info(f"Paid ${amount:.2f} in dividends to user {user_id}")
    
    @classmethod
    def process_daily_dividends(cls) -> Dict[str, Dict[str, float]]:
        """
        Process daily dividend payments and return summary data.
        
        Returns:
            Dictionary with two sub-dictionaries:
            - 'top_shareholders': Maps user IDs to dividend amounts for top shareholders
            - 'creators': Maps user IDs to dividend amounts for stock creators
        """
        # Load all user data
        user_data = DataManager.load_data(config.USER_DATA_FILE)
        
        # Today's date in EST
        utc_now = datetime.now(pytz.utc)
        eastern = pytz.timezone("America/New_York")
        est_now = utc_now.astimezone(eastern)
        today = est_now.strftime("%Y-%m-%d")
        
        # Track dividends for each user by type
        shareholder_dividends = {}
        creator_dividends = {}
        
        # Process each stock
        for symbol in StockManager.get_all_symbols():
            if symbol not in StockManager.stock_prices:
                continue
                
            # Get current stock price
            stock_price = StockManager.stock_prices[symbol]
            
            # Skip stocks with zero or negative price
            if stock_price <= 0:
                continue
                
            # 1. Find all shareholders and their holdings
            shareholders = cls._get_shareholders(user_data, symbol)
            
            # 2. Pay dividends to top shareholders
            cls._calculate_top_shareholder_dividends(symbol, stock_price, shareholders, shareholder_dividends)
            
            # 3. Pay dividends to stock creator
            cls._calculate_creator_dividends(symbol, stock_price, shareholders, creator_dividends)
        
        # Apply all dividends to user balances and record last dividend date
        for user_id in set(list(shareholder_dividends.keys()) + list(creator_dividends.keys())):
            # Ensure user exists
            DataManager.ensure_user(user_id)
            
            # Calculate total dividend
            total_dividend = shareholder_dividends.get(user_id, 0) + creator_dividends.get(user_id, 0)
            
            if total_dividend > 0:
                # Add dividend to balance
                UserManager.update_balance(user_id, total_dividend)
                
                # Record last dividend date
                data = DataManager.load_data(config.USER_DATA_FILE)
                if "last_dividend" not in data[user_id]:
                    data[user_id]["last_dividend"] = {}
                data[user_id]["last_dividend"]["date"] = today
                data[user_id]["last_dividend"]["amount"] = total_dividend
                DataManager.save_data(config.USER_DATA_FILE, data)
                
                logger.info(f"Paid ${total_dividend:.2f} in daily dividends to user {user_id}")
        
        return {
            "top_shareholders": shareholder_dividends,
            "creators": creator_dividends
        }
    
    @classmethod
    def _calculate_top_shareholder_dividends(cls, symbol: str, stock_price: float, 
                                           shareholders: List[Tuple[str, int]], dividends: Dict[str, float]) -> None:
        """
        Calculate dividends for top shareholders for daily payouts.
        
        Args:
            symbol: Stock symbol
            stock_price: Current stock price
            shareholders: List of (user_id, shares) tuples sorted by shares
            dividends: Dictionary tracking dividend amounts by user
        """
        # Pay dividends to top shareholders (if any)
        for rank, (user_id, shares) in enumerate(shareholders[:cls.TOP_SHAREHOLDERS_COUNT]):
            if rank in cls.TOP_SHAREHOLDER_DIVIDENDS:
                # Calculate dividend based on rank and stock price
                percent = cls.TOP_SHAREHOLDER_DIVIDENDS[rank]
                dividend_amount = round(stock_price * (percent / 100), 2)
                
                # Add to user's dividend total
                if user_id not in dividends:
                    dividends[user_id] = 0
                dividends[user_id] += dividend_amount
    
    @classmethod
    def _calculate_creator_dividends(cls, symbol: str, stock_price: float, 
                                    shareholders: List[Tuple[str, int]], dividends: Dict[str, float]) -> None:
        """
        Calculate dividends for stock creator for daily payouts.
        
        Args:
            symbol: Stock symbol
            stock_price: Current stock price
            shareholders: List of (user_id, shares) tuples
            dividends: Dictionary tracking dividend amounts by user
        """
        # Find creator of this stock
        creator_id = None
        for user_id, ticker in StockManager.user_to_ticker.items():
            if ticker == symbol:
                creator_id = user_id
                break
        
        if not creator_id:
            return  # No creator found for this stock
        
        # Count shares held by other users (excluding creator)
        total_other_shares = 0
        for user_id, shares in shareholders:
            if user_id != creator_id:
                total_other_shares += shares
        
        # Calculate creator dividend based on other holders
        if total_other_shares > 0:
            # Base dividend on stock price and number of shares others hold
            dividend_amount = round(stock_price * (cls.CREATOR_DIVIDEND_PERCENT / 100) * total_other_shares, 2)
            
            # Add to creator's dividend total
            if creator_id not in dividends:
                dividends[creator_id] = 0
            dividends[creator_id] += dividend_amount