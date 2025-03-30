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
        Calculate popularity score for each stock based only on total shares held.
        
        Returns:
            Dictionary mapping stock symbols to their total shares held
        """
        # Load user data
        user_data = DataManager.load_data(config.USER_DATA_FILE)
        all_symbols = StockManager.get_all_symbols()
        
        # Initialize total shares counter for each stock
        total_shares = {symbol: 0 for symbol in all_symbols}
        
        # Count total shares for each stock
        for user_id, data in user_data.items():
            inventory = data.get("inventory", {})
            for stock, quantity in inventory.items():
                if stock in total_shares and quantity > 0:
                    total_shares[stock] += quantity
        
        # Add a tiny value based on symbol to avoid ties and ensure consistent sorting
        popularity_scores = {}
        for symbol, shares in total_shares.items():
            # Add a tiny fraction based on symbol name for tie-breaking
            symbol_value = sum(ord(c) / 10000.0 for c in symbol)
            popularity_scores[symbol] = shares + symbol_value
            
            # Log the calculation
            logger.debug(f"Stock {symbol}: {shares} total shares, score: {popularity_scores[symbol]}")
        
        return popularity_scores
    
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