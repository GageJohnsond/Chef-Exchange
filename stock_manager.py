"""
Stock market simulation module for CH3F Exchange Discord Bot
Handles stock data, market conditions, and price updates
"""
import json
import random
import logging
import pytz
from datetime import datetime, timezone
from typing import Dict, Any, List, Tuple, Optional, Union
from io import BytesIO

import matplotlib.pyplot as plt
import matplotlib.image as mpimg
import matplotlib.dates as mdates
from matplotlib.ticker import MaxNLocator

import config

logger = logging.getLogger('ch3f_exchange.stocks')

class StockManager:
    """Class to handle all stock market simulation logic"""
    
    # Global stock data
    stock_prices = {}        # Current prices for all stocks
    price_history = {}       # Historical prices for all stocks
    stock_messages = {}      # Discord message IDs for stock charts
    
    # Market condition variables
    current_min_change = config.STOCK_PRICE_MIN_CHANGE 
    current_max_change = config.STOCK_PRICE_MAX_CHANGE
    market_condition = "stable"
    last_condition_change = None
    
    # File paths
    STOCKS_FILE = config.STOCKS_FILE
    STOCK_MESSAGES_FILE = config.STOCK_MESSAGES_FILE
    
    @classmethod
    def initialize(cls) -> bool:
        """Initialize the stock market system"""
        try:
            # Load existing stock data or generate new
            cls.load_stocks()
            
            # Load message IDs
            cls.load_stock_messages()
            
            logger.info(f"Stock market initialized. Current market: {cls.market_condition}")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize stock market: {e}", exc_info=True)
            return False
    
    @classmethod
    def load_stocks(cls) -> None:
        """Load stock data from file or generate new if needed"""
        try:
            with open(cls.STOCKS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            # Validate required fields exist
            required_fields = ["STOCK_PRICES", "PRICE_HISTORY"]
            if all(field in data for field in required_fields):
                cls.stock_prices = data["STOCK_PRICES"]
                cls.price_history = data["PRICE_HISTORY"]
                
                # Load market conditions if available
                if "MARKET_CONDITION" in data:
                    cls.market_condition = data["MARKET_CONDITION"]
                if "CURRENT_MIN_CHANGE" in data:
                    cls.current_min_change = data["CURRENT_MIN_CHANGE"]
                if "CURRENT_MAX_CHANGE" in data:
                    cls.current_max_change = data["CURRENT_MAX_CHANGE"]
                if "LAST_CONDITION_CHANGE" in data:
                    cls.last_condition_change = data["LAST_CONDITION_CHANGE"]
                    
                logger.info(f"✅ Loaded existing stock data. Market: {cls.market_condition}")
                return
            else:
                logger.warning("⚠️ stocks.json is missing required fields. Regenerating stock data...")
        
        except (json.JSONDecodeError, IOError, FileNotFoundError):
            logger.error("❌ Error: stocks.json is missing or corrupted. Regenerating stock data...")
        
        # If we get here, we need to generate new stock data
        cls._generate_new_stocks()
    
    @classmethod
    def save_stocks(cls) -> None:
        """Save current stock data to file"""
        data = {
            "STOCK_PRICES": cls.stock_prices,
            "PRICE_HISTORY": cls.price_history,
            "MARKET_CONDITION": cls.market_condition,
            "CURRENT_MIN_CHANGE": cls.current_min_change,
            "CURRENT_MAX_CHANGE": cls.current_max_change,
            "LAST_CONDITION_CHANGE": cls.last_condition_change
        }
        
        try:
            with open(cls.STOCKS_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
            logger.debug("💾 Stock data saved successfully.")
        except Exception as e:
            logger.error(f"Error saving stock data: {e}")
    
    @classmethod
    def _generate_new_stocks(cls) -> None:
        """Generate new stock data from scratch"""
        # Create initial stock prices
        cls.stock_prices = {
            symbol: round(random.uniform(
                config.NEW_STOCK_MIN_PRICE, 
                config.NEW_STOCK_MAX_PRICE), 2) 
            for symbol in config.STOCK_SYMBOLS
        }
        
        # Initialize price history with starting prices
        cls.price_history = {
            symbol: [cls.stock_prices[symbol]] 
            for symbol in config.STOCK_SYMBOLS
        }
        
        # Set initial market condition
        cls.market_condition = "stable"
        cls.current_min_change = config.STOCK_PRICE_MIN_CHANGE
        cls.current_max_change = config.STOCK_PRICE_MAX_CHANGE
        cls.last_condition_change = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        
        # Save the new data
        cls.save_stocks()
        logger.info("🔄 New stock data generated and saved.")
    
    @classmethod
    def load_stock_messages(cls) -> None:
        """Load message IDs for stock charts"""
        try:
            if open(cls.STOCK_MESSAGES_FILE, "a").close() or True:  # Create file if it doesn't exist
                with open(cls.STOCK_MESSAGES_FILE, "r", encoding="utf-8") as f:
                    try:
                        cls.stock_messages = json.load(f)
                        logger.info(f"Loaded {len(cls.stock_messages)} stock message IDs")
                    except json.JSONDecodeError:
                        # File exists but is invalid JSON
                        cls.stock_messages = {}
                        logger.warning("Stock messages file corrupted. Reset to empty.")
        except Exception as e:
            logger.error(f"Error loading stock messages: {e}")
            cls.stock_messages = {}
    
    @classmethod
    def save_stock_messages(cls) -> None:
        """Save message IDs for stock charts"""
        try:
            with open(cls.STOCK_MESSAGES_FILE, "w", encoding="utf-8") as f:
                json.dump(cls.stock_messages, f, indent=4)
            logger.debug("Stock message IDs saved.")
        except Exception as e:
            logger.error(f"Error saving stock message IDs: {e}")
    
    @classmethod
    def check_market_condition(cls) -> None:
        """
        Check and potentially update market condition based on daily schedule.
        """
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        
        # Skip if already updated today
        if cls.last_condition_change == today:
            return
        
        # Define possible market conditions with their properties
        conditions = [
            {
                "name": "bear", 
                "weight": 0.2,
                "min_change": random.uniform(-4, -1),
                "max_change": random.uniform(-1, 2),
            },
            {
                "name": "bull", 
                "weight": 0.2,
                "min_change": random.uniform(-1, 1),
                "max_change": random.uniform(2, 4),
            },
            {
                "name": "volatile", 
                "weight": 0.2,
                "min_change": random.uniform(-7, -3),
                "max_change": random.uniform(3, 7),
            },
            {
                "name": "stable", 
                "weight": 0.4,
                "min_change": random.uniform(-3, -1),
                "max_change": random.uniform(1, 3),
            }
        ]
        
        # Choose new market condition weighted by probabilities
        weights = [c["weight"] for c in conditions]
        new_condition = random.choices(conditions, weights=weights, k=1)[0]
        
        # Update market state
        cls.market_condition = new_condition["name"]
        cls.current_min_change = new_condition["min_change"]
        cls.current_max_change = new_condition["max_change"]
        cls.last_condition_change = today
        
        # Save the changes
        cls.save_stocks()
        
        logger.info(f"Market condition changed to {cls.market_condition}: " 
                    f"min={cls.current_min_change:.2f}, max={cls.current_max_change:.2f}")
    
    @classmethod
    def update_prices(cls) -> None:
        """
        Update all stock prices based on current market condition.
        """
        # Check if market condition needs to be updated
        cls.check_market_condition()
        
        # Update each stock price based on current market condition
        for symbol in config.STOCK_SYMBOLS:
            # Get base change within current market condition bounds
            change = random.uniform(cls.current_min_change, cls.current_max_change)
            
            # Apply some stock-specific variation (±20% of the base change)
            variation = change * random.uniform(-0.2, 0.2)
            final_change = change + variation
            
            # Calculate new price (minimum of 1.0)
            new_price = max(1.0, cls.stock_prices[symbol] + final_change)
            cls.stock_prices[symbol] = round(new_price, 2)
            cls.price_history[symbol].append(round(new_price, 2))
            
            # Keep history at last 100 updates
            if len(cls.price_history[symbol]) > 100:
                cls.price_history[symbol] = cls.price_history[symbol][-100:]
        
        # Save the updated stock data
        cls.save_stocks()
    
    @classmethod
    def buy_stock(cls, symbol: str, user_id: str) -> float:
        """
        Process a stock purchase and return the purchase price.
        Also updates the stock price to reflect the purchase and records purchase date.
        
        Args:
            symbol: The stock symbol to buy
            user_id: The ID of the user making the purchase
        
        Returns:
            The purchase price
        """
        # Get current price
        price = cls.stock_prices[symbol]
        
        # Record purchase date in user data
        from data_manager import DataManager
        data = DataManager.load_data(config.USER_DATA_FILE)
        if str(user_id) in data:
            # Initialize purchase_dates if it doesn't exist
            if "purchase_dates" not in data[str(user_id)]:
                data[str(user_id)]["purchase_dates"] = {}
            
            # Get current date
            utc_now = datetime.now(pytz.utc)
            eastern = pytz.timezone("America/New_York")
            est_now = utc_now.astimezone(eastern)
            today = est_now.strftime("%Y-%m-%d")
            
            # Record this purchase
            if symbol not in data[str(user_id)]["purchase_dates"]:
                data[str(user_id)]["purchase_dates"][symbol] = []
            
            data[str(user_id)]["purchase_dates"][symbol].append(today)
            
            # Save the updated data
            DataManager.save_data(config.USER_DATA_FILE, data)
        
        # Increase stock price after purchase (market impact)
        change = random.uniform(config.STOCK_BUY_MIN_CHANGE, config.STOCK_BUY_MAX_CHANGE)
        new_price = max(1.0, cls.stock_prices[symbol] + change)
        cls.stock_prices[symbol] = round(new_price, 2)
        cls.price_history[symbol].append(round(new_price, 2))
        
        # Save changes
        cls.save_stocks()
        return price
    
    @classmethod
    def sell_stock(cls, symbol: str, user_id: str) -> Tuple[float, bool]:
        """
        Process a stock sale and return the sale price.
        Applies selling fee only if stock was purchased on the same day.
        Also updates the stock price to reflect the sale.
        
        Args:
            symbol: The stock symbol to sell
            user_id: The ID of the user making the sale
        
        Returns:
            Tuple of (sale price, was same day sale)
        """
        # Get current price 
        base_price = cls.stock_prices[symbol]
        same_day_sale = False
        fee = 0
        
        # Check if this is a same-day sale
        from data_manager import DataManager
        data = DataManager.load_data(config.USER_DATA_FILE)
        if str(user_id) in data and "purchase_dates" in data[str(user_id)]:
            purchase_dates = data[str(user_id)].get("purchase_dates", {})
            if symbol in purchase_dates and purchase_dates[symbol]:
                utc_now = datetime.now(pytz.utc)
                eastern = pytz.timezone("America/New_York")
                est_now = utc_now.astimezone(eastern)
                today = est_now.strftime("%Y-%m-%d")
                
                # Check if any purchases were made today
                if today in purchase_dates[symbol]:
                    same_day_sale = True
                    fee = config.SELLING_FEE
                    
                    # Remove one instance of today's purchase date
                    purchase_dates[symbol].remove(today)
                    
                    # Save the updated purchase dates
                    DataManager.save_data(config.USER_DATA_FILE, data)
        
        # Calculate sale price after fee (if applicable)
        sale_price = base_price - fee
        
        # Decrease stock price after sale (market impact)
        change = random.uniform(config.STOCK_SELL_MIN_CHANGE, config.STOCK_SELL_MAX_CHANGE)
        new_price = max(1.0, cls.stock_prices[symbol] - change)
        cls.stock_prices[symbol] = round(new_price, 2)
        cls.price_history[symbol].append(round(new_price, 2))
        
        # Save changes
        cls.save_stocks()
        return sale_price, same_day_sale
    
    @classmethod
    def get_stock_info(cls, symbol: str) -> Dict[str, Any]:
        """Get comprehensive information about a stock"""
        if symbol not in cls.stock_prices:
            return {"error": "Stock not found"}
        
        current_price = cls.stock_prices[symbol]
        history = cls.price_history[symbol]
        
        # Calculate changes
        day_change = 0
        week_change = 0
        
        if len(history) > 1:
            day_change = ((current_price - history[-2]) / history[-2]) * 100
        
        if len(history) > 7:
            week_change = ((current_price - history[-7]) / history[-7]) * 100
        
        # Get overall trend direction
        if len(history) > 10:
            recent_prices = history[-10:]
            direction = "neutral"
            
            # Simple trend analysis based on last 10 updates
            upward_moves = sum(1 for i in range(1, len(recent_prices)) 
                              if recent_prices[i] > recent_prices[i-1])
            downward_moves = len(recent_prices) - 1 - upward_moves
            
            if upward_moves > downward_moves * 1.5:
                direction = "strong upward"
            elif upward_moves > downward_moves:
                direction = "upward"
            elif downward_moves > upward_moves * 1.5:
                direction = "strong downward"
            elif downward_moves > upward_moves:
                direction = "downward"
        else:
            direction = "insufficient data"
        
        return {
            "symbol": symbol,
            "price": current_price,
            "day_change_pct": day_change,
            "week_change_pct": week_change,
            "trend": direction,
            "history": history,
            "market_condition": cls.market_condition
        }
    
    @classmethod
    def get_top_performers(cls, timeframe: str = "day") -> List[Dict[str, Any]]:
        """Get top performing stocks for a given timeframe (day, week, all)"""
        results = []
        
        for symbol in cls.stock_prices.keys():
            history = cls.price_history[symbol]
            current_price = cls.stock_prices[symbol]
            
            if timeframe == "day" and len(history) > 1:
                change_pct = ((current_price - history[-2]) / history[-2]) * 100
                results.append({"symbol": symbol, "price": current_price, "change_pct": change_pct})
            
            elif timeframe == "week" and len(history) > 7:
                change_pct = ((current_price - history[-7]) / history[-7]) * 100
                results.append({"symbol": symbol, "price": current_price, "change_pct": change_pct})
            
            elif timeframe == "all" and len(history) > 1:
                change_pct = ((current_price - history[0]) / history[0]) * 100
                results.append({"symbol": symbol, "price": current_price, "change_pct": change_pct})
        
        # Sort by percent change (descending)
        results.sort(key=lambda x: x["change_pct"], reverse=True)
        return results
    
    @classmethod
    def generate_stock_chart(cls, symbol: str) -> BytesIO:
        """Generate a stock chart for a given symbol"""
        # Create figure with proper size
        fig, ax = plt.subplots(figsize=(6, 5))
        
        # Add logo if file exists
        try:
            logo = mpimg.imread(config.LOGO_FILE)
            logo_ax = fig.add_axes([0.3, 0.9, 0.4, 0.1])
            logo_ax.imshow(logo)
            logo_ax.axis("off")
        except FileNotFoundError:
            logger.warning(f"Logo file '{config.LOGO_FILE}' not found, skipping")
        
        # Plot the stock price history
        history = cls.price_history[symbol]
        x_values = list(range(len(history)))
        
        # Calculate color based on trend
        if len(history) > 1:
            color = 'green' if history[-1] >= history[0] else 'red'
        else:
            color = 'blue'
            
        ax.plot(x_values, history, color=color, linestyle='-')
        
        # Add labels and grid
        ax.set_xlabel("Time Steps")
        ax.set_ylabel(f"{symbol} Price (CCD)")
        ax.grid(True)
        
        # Add watermark
        ax.text(
            0.5, 0.5, symbol, 
            fontsize=50, color='gray', alpha=0.2,
            ha='center', va='center', transform=ax.transAxes, fontweight='bold'
        )
        
        # Save to buffer
        buf = BytesIO()
        plt.savefig(buf, format='png', bbox_inches='tight')
        buf.seek(0)
        plt.close()
        
        return buf

    @classmethod
    def get_user_portfolio_value(cls, inventory: Dict[str, int]) -> float:
        """Calculate the total value of a user's stock portfolio"""
        total_value = 0
        for stock, quantity in inventory.items():
            if stock in cls.stock_prices:
                stock_value = cls.stock_prices[stock] * quantity
                total_value += stock_value
        return total_value
    
    @classmethod
    def get_market_summary(cls) -> Dict[str, Any]:
        """Get a summary of current market conditions"""
        num_stocks = len(cls.stock_prices)
        up_stocks = sum(1 for s in config.STOCK_SYMBOLS 
                        if len(cls.price_history[s]) > 1 and 
                        cls.stock_prices[s] > cls.price_history[s][-2])
        
        down_stocks = sum(1 for s in config.STOCK_SYMBOLS 
                          if len(cls.price_history[s]) > 1 and 
                          cls.stock_prices[s] < cls.price_history[s][-2])
        
        flat_stocks = num_stocks - up_stocks - down_stocks
        
        # Get average price and change
        total_price = sum(cls.stock_prices[s] for s in config.STOCK_SYMBOLS)
        avg_price = total_price / num_stocks if num_stocks > 0 else 0
        
        # Calculate market index (average of all prices)
        market_index = avg_price
        
        # Calculate market index change if we have history
        index_change = 0
        if all(len(cls.price_history[s]) > 1 for s in config.STOCK_SYMBOLS):
            prev_total = sum(cls.price_history[s][-2] for s in config.STOCK_SYMBOLS)
            prev_index = prev_total / num_stocks if num_stocks > 0 else 0
            index_change = ((market_index - prev_index) / prev_index) * 100 if prev_index > 0 else 0
        
        return {
            "market_condition": cls.market_condition,
            "price_range": {
                "min": cls.current_min_change,
                "max": cls.current_max_change
            },
            "market_index": market_index,
            "index_change_pct": index_change,
            "stocks": {
                "total": num_stocks,
                "up": up_stocks,
                "down": down_stocks,
                "flat": flat_stocks
            },
            "last_update": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        }