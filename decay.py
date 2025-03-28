"""
Stock decay system for the Exchange Discord Bot
Applies price decay to least popular stocks when the total number exceeds a threshold
"""
import logging
from typing import List, Tuple, Dict

import config
from data_manager import DataManager
from stock_manager import StockManager

logger = logging.getLogger('stock_exchange.decay')

class DecayManager:
    """Class to handle stock decay for least popular stocks"""
    
    @classmethod
    def apply_stock_decay(cls) -> List[str]:
        """
        Apply decay to least popular stocks when total stock count exceeds threshold.
        
        Returns:
            List of symbols that were decayed
        """
        # Get total number of stocks
        total_stocks = len(StockManager.get_all_symbols())
        
        # Check if total exceeds threshold
        if total_stocks <= config.STOCK_DECAY_THRESHOLD:
            logger.debug(f"Stock count ({total_stocks}) under decay threshold ({config.STOCK_DECAY_THRESHOLD}). No decay applied.")
            return []
        
        # Calculate how many stocks should decay
        excess_stocks = total_stocks - config.STOCK_DECAY_THRESHOLD
        logger.info(f"Stock decay triggered: {excess_stocks} stocks over threshold")
        
        # Get popularity data for each stock
        stock_popularity = cls._calculate_stock_popularity()
        
        # Sort by popularity (ascending, least popular first)
        sorted_stocks = sorted(stock_popularity.items(), key=lambda x: x[1])
        
        # Get the least popular stocks up to the excess count
        stocks_to_decay = sorted_stocks[:excess_stocks]
        
        # Apply decay to each stock
        decayed_stocks = []
        for symbol, _ in stocks_to_decay:
            if symbol in StockManager.stock_prices:
                # Apply decay percentage
                current_price = StockManager.stock_prices[symbol]
                new_price = current_price * (1 - config.STOCK_DECAY_PERCENT / 100)
                
                # Round to 2 decimal places
                new_price = round(max(0.01, new_price), 2)  # Minimum price of $0.01
                
                # Update price
                StockManager.stock_prices[symbol] = new_price
                
                # Add to price history
                StockManager.price_history[symbol].append(new_price)
                
                # Log the decay
                logger.info(f"Applied {config.STOCK_DECAY_PERCENT}% decay to {symbol}: ${current_price:.2f} -> ${new_price:.2f}")
                
                # Add to list of decayed stocks
                decayed_stocks.append(symbol)
                
                # Check for potential bankruptcy from decay
                if new_price <= config.STOCK_BANKRUPTCY_THRESHOLD:
                    logger.warning(f"Stock {symbol} is close to bankruptcy from decay: ${new_price:.2f}")
        
        # Save stock changes
        StockManager.save_stocks()
        
        return decayed_stocks
    
    @classmethod
    def _calculate_stock_popularity(cls) -> Dict[str, int]:
        """
        Calculate popularity score for each stock based on number of shareholders.
        
        Returns:
            Dictionary mapping stock symbols to their popularity score
        """
        # Load user data
        user_data = DataManager.load_data(config.USER_DATA_FILE)
        
        # Count shareholders for each stock
        stock_holders = {symbol: 0 for symbol in StockManager.get_all_symbols()}
        
        for user_id, data in user_data.items():
            inventory = data.get("inventory", {})
            
            for stock, quantity in inventory.items():
                if stock in stock_holders and quantity > 0:
                    stock_holders[stock] += 1
        
        # Calculate popularity score (currently just shareholder count)
        # This could be expanded to include other factors like trading volume, etc.
        stock_popularity = {}
        
        for symbol, holders in stock_holders.items():
            # Get creator user_id for this stock
            creator_id = None
            for user_id, ticker in StockManager.user_to_ticker.items():
                if ticker == symbol:
                    creator_id = user_id
                    break
            
            # Add to popularity score when stock is owned by the creator
            creator_score = 1 if creator_id in user_data and symbol in user_data[creator_id].get("inventory", {}) else 0
            
            # Final popularity score calculation
            stock_popularity[symbol] = holders + creator_score
        
        return stock_popularity
    
    @classmethod
    def get_decay_risk_stocks(cls) -> List[Tuple[str, float]]:
        """
        Returns a list of stocks at risk of decay based on current popularity.
        
        Returns:
            List of (symbol, risk_factor) tuples where risk_factor is 0-100
        """
        # Get total number of stocks
        total_stocks = len(StockManager.get_all_symbols())
        
        # If under threshold, no risk
        if total_stocks <= config.STOCK_DECAY_THRESHOLD:
            return []
        
        # Calculate excess
        excess_stocks = total_stocks - config.STOCK_DECAY_THRESHOLD
        
        # Get popularity ratings
        stock_popularity = cls._calculate_stock_popularity()
        
        # Sort by popularity (ascending)
        sorted_stocks = sorted(stock_popularity.items(), key=lambda x: x[1])
        
        # Get decay risk stocks (excess count plus a buffer)
        buffer = min(3, len(sorted_stocks) - excess_stocks)  # Up to 3 additional stocks as buffer
        risk_count = excess_stocks + buffer
        
        # Calculate risk factor - 100% for stocks that will definitely decay,
        # lower percentages for buffer stocks
        risk_stocks = []
        for i, (symbol, popularity) in enumerate(sorted_stocks[:risk_count]):
            if i < excess_stocks:
                risk_factor = 100.0  # Definitely will decay
            else:
                # Calculate risk factor for buffer stocks (100% to 25%)
                buffer_position = i - excess_stocks
                risk_factor = 100 - (buffer_position * 75 / buffer if buffer > 0 else 0)
            
            risk_stocks.append((symbol, risk_factor))
        
        return risk_stocks