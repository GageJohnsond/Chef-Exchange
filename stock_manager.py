"""
Stock market simulation module for Discord Exchange Bot
Handles stock data, market conditions, and price updates
"""
import discord
import json
import random
import logging
import pytz
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Tuple, Optional, Union
from io import BytesIO

import matplotlib.pyplot as plt
import matplotlib.image as mpimg
import matplotlib.dates as mdates
from matplotlib.ticker import MaxNLocator

import config

logger = logging.getLogger('stock_exchange.stocks')

class StockManager:
    """Class to handle all stock market simulation logic"""
    
    # Global stock data
    stock_symbols = []        # List of active stock symbols
    user_to_ticker = {}       # Mapping of user ID to their stock symbol
    stock_prices = {}         # Current prices for all stocks
    price_history = {}        # Historical prices for all stocks
    stock_messages = {}       # Discord message IDs for stock charts
    
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
            
            # Validate required fields exist in old format (backward compatibility)
            required_fields = ["STOCK_PRICES", "PRICE_HISTORY"]
            if all(field in data for field in required_fields):
                cls.stock_prices = data["STOCK_PRICES"]
                cls.price_history = data["PRICE_HISTORY"]
                
                # Load symbols and mappings if available in new format
                if "STOCK_SYMBOLS" in data:
                    # Make sure stock_symbols is a list
                    if isinstance(data["STOCK_SYMBOLS"], list):
                        cls.stock_symbols = data["STOCK_SYMBOLS"]
                    else:
                        # Convert from dict or other type to list
                        logger.warning("Converting STOCK_SYMBOLS from non-list to list")
                        cls.stock_symbols = list(data["STOCK_SYMBOLS"].keys() if isinstance(data["STOCK_SYMBOLS"], dict) 
                                            else data["STOCK_SYMBOLS"])
                else:
                    # Fallback to config for backward compatibility
                    cls.stock_symbols = list(config.STOCK_SYMBOLS)
                
                if "USER_TO_TICKER" in data:
                    cls.user_to_ticker = data["USER_TO_TICKER"]
                else:
                    # Fallback to config for backward compatibility
                    cls.user_to_ticker = dict(config.USER_TO_TICKER)
                
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
            "STOCK_SYMBOLS": cls.stock_symbols,
            "USER_TO_TICKER": cls.user_to_ticker,
            "MARKET_CONDITION": cls.market_condition,
            "CURRENT_MIN_CHANGE": cls.current_min_change,
            "CURRENT_MAX_CHANGE": cls.current_max_change,
            "LAST_CONDITION_CHANGE": cls.last_condition_change
        }
        
        try:
            with open(cls.STOCKS_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=0)
            logger.debug("💾 Stock data saved successfully.")
        except Exception as e:
            logger.error(f"Error saving stock data: {e}")
    
    @classmethod
    def _generate_new_stocks(cls) -> None:
        """Generate new stock data from scratch"""
        # Initialize with values from config for the first run
        cls.stock_symbols = list(config.STOCK_SYMBOLS)
        cls.user_to_ticker = dict(config.USER_TO_TICKER)
        
        # Create initial stock prices
        cls.stock_prices = {
            symbol: round(random.uniform(
                config.NEW_STOCK_MIN_PRICE, 
                config.NEW_STOCK_MAX_PRICE), 2) 
            for symbol in cls.stock_symbols
        }
        
        # Initialize price history with starting prices
        cls.price_history = {
            symbol: [cls.stock_prices[symbol]] 
            for symbol in cls.stock_symbols
        }
        
        # Set initial market condition
        cls.market_condition = "stable"
        cls.current_min_change = config.STOCK_PRICE_MIN_CHANGE
        cls.current_max_change = config.STOCK_PRICE_MAX_CHANGE
        
        # Set initial condition change time using full timestamp
        cls.last_condition_change = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        
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
                json.dump(cls.stock_messages, f, indent=0)
            logger.debug("Stock message IDs saved.")
        except Exception as e:
            logger.error(f"Error saving stock message IDs: {e}")

    @classmethod
    def get_all_symbols(cls) -> list:
        return cls.stock_symbols
    
    @classmethod
    def get_user_stock(cls, user_id) -> str:
        return cls.user_to_ticker.get(str(user_id))
    
    @classmethod
    def check_market_condition(cls) -> None:
        """
        Check and potentially update market condition based on 9-hour schedule.
        """
        now = datetime.now(timezone.utc)
        current_time = now.strftime("%Y-%m-%d %H:%M:%S")
        
        # Format last condition change time if it exists
        if cls.last_condition_change:
            try:
                # Try to parse the stored datetime string
                last_change_time = datetime.strptime(cls.last_condition_change, "%Y-%m-%d %H:%M:%S")
                # Add timezone info
                last_change_time = last_change_time.replace(tzinfo=timezone.utc)
                
                # Check if 6 hours have passed
                time_diff = now - last_change_time
                hours_passed = time_diff.total_seconds() / 3600
                
                # If less than 6 hours have passed, don't update
                if hours_passed < 9:
                    return
                    
            except ValueError:
                # If there's an error parsing the date, force an update
                logger.warning("Could not parse last condition change time. Forcing market update.")
        
        # Define possible market conditions with their properties
        conditions = [
            {
                "name": "bear", 
                "weight": 0.2,
                "min_change": random.uniform(-5, -1),
                "max_change": random.uniform(0, 2),
            },
            {
                "name": "bull", 
                "weight": 0.2,
                "min_change": random.uniform(-.5, 1),
                "max_change": random.uniform(2, 5.5),
            },
            {
                "name": "superbull", 
                "weight": 0.02,
                "min_change": random.uniform(0, 1),
                "max_change": random.uniform(4, 8),
            },
            {
                "name": "volatile", 
                "weight": 0.2,
                "min_change": random.uniform(-8, -3),
                "max_change": random.uniform(3, 8),
            },
            {
                "name": "stable", 
                "weight": 0.35,  
                "min_change": random.uniform(-4, -1),
                "max_change": random.uniform(1, 4),
            },
            {
                "name": "crash", 
                "weight": 0.03,  
                "min_change": random.uniform(-12, -8),
                "max_change": random.uniform(-8, -4),
            }
        ]
        
        # Choose new market condition weighted by probabilities
        weights = [c["weight"] for c in conditions]
        new_condition = random.choices(conditions, weights=weights, k=1)[0]
        
        # Update market state
        cls.market_condition = new_condition["name"]
        cls.current_min_change = new_condition["min_change"]
        cls.current_max_change = new_condition["max_change"]
        cls.last_condition_change = current_time
        
        # Save the changes
        cls.save_stocks()
        
        # Log the market condition change with more prominent message for crash
        if cls.market_condition == "crash":
            logger.warning(f"🔴 MARKET CRASH DETECTED! Market condition changed to {cls.market_condition}: " 
                        f"min={cls.current_min_change:.2f}, max={cls.current_max_change:.2f}")
        else:
            logger.info(f"Market condition changed to {cls.market_condition}: " 
                        f"min={cls.current_min_change:.2f}, max={cls.current_max_change:.2f}")
    @classmethod
    async def update_prices(cls) -> None:
        """
        Update all stock prices based on current market condition.
        Allow stocks to go bankrupt if they reach 0 or below.
        """
        # Check if market condition needs to be updated
        cls.check_market_condition()
        
        # Keep track of stocks that went bankrupt
        bankrupt_stocks = []
        bankruptcy_announcements = {}
        
        # Update each stock price based on current market condition
        # Use a copy of the list since we might modify it during iteration
        current_symbols = list(cls.stock_symbols)
        
        for symbol in current_symbols:
            # First check if the stock is already at or below 0
            if symbol in cls.stock_prices and cls.stock_prices[symbol] <= 0:
                bankrupt_stocks.append(symbol)
                continue
                
            # Get base change within current market condition bounds
            change = random.uniform(cls.current_min_change, cls.current_max_change)
            
            # Apply some stock-specific variation (±20% of the base change)
            variation = change * random.uniform(-0.2, 0.2)
            final_change = change + variation
            
            # Calculate new price
            current_price = cls.stock_prices.get(symbol, 0)
            new_price = current_price + final_change
            new_price = round(new_price, 2)
            
            # Check for bankruptcy (price <= 0)
            if new_price <= 0:
                # Mark for bankruptcy instead of updating the price
                bankrupt_stocks.append(symbol)
                # Set the price to exactly 0 for clean handling
                cls.stock_prices[symbol] = 0
                cls.price_history[symbol].append(0)
            else:
                # Only update the price if it's above 0
                cls.stock_prices[symbol] = new_price
                cls.price_history[symbol].append(new_price)
                
                # Keep history at last 175 updates for active stocks
                if len(cls.price_history[symbol]) > 175:
                    cls.price_history[symbol] = cls.price_history[symbol][-175:]
        
        # Handle bankrupt stocks
        for symbol in bankrupt_stocks:
            if symbol in cls.stock_prices:  # Double-check the stock exists
                try:
                    announcement_data = await cls.handle_bankruptcy(symbol)
                    bankruptcy_announcements[symbol] = announcement_data
                    logger.warning(f"Stock {symbol} has gone bankrupt and has been removed from the system")
                except Exception as e:
                    logger.error(f"Error handling bankruptcy for {symbol}: {e}", exc_info=True)
        
        # Save the updated stock data
        cls.save_stocks()
        
        # Return bankruptcy announcements for potential notifications
        return bankruptcy_announcements
    
    @classmethod
    async def add_stock(cls, symbol, user_id) -> bool:
        try:
            # Ensure stock_symbols is a list
            if not isinstance(cls.stock_symbols, list):
                cls.stock_symbols = list(cls.stock_symbols.keys()) if isinstance(cls.stock_symbols, dict) else []
                logger.warning(f"Converted stock_symbols to list: {cls.stock_symbols}")
            
            # Add to internal data structures
            cls.stock_symbols.append(symbol)
            cls.user_to_ticker[str(user_id)] = symbol
            
            # Initialize price and history
            starting_price = round(random.uniform(config.NEW_STOCK_MIN_PRICE, config.NEW_STOCK_MAX_PRICE), 2)
            cls.stock_prices[symbol] = starting_price
            cls.price_history[symbol] = [starting_price]
            
            # Save changes
            cls.save_stocks()
            logger.info(f"Added new stock {symbol} for user {user_id}")
            return True
        except Exception as e:
            logger.error(f"Error adding new stock {symbol}: {e}")
            return False
    
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
        new_price = cls.stock_prices[symbol] + change
        cls.stock_prices[symbol] = round(new_price, 2)
        cls.price_history[symbol].append(round(new_price, 2))
        
        # Save changes
        cls.save_stocks()
        return price
        
    @classmethod
    async def sell_stock(cls, symbol: str, user_id: str, bot=None) -> Tuple[float, bool, bool]:
        """
        Process a stock sale and return the sale price.
        Applies selling fee only if stock was purchased on the same day.
        Also updates the stock price to reflect the sale.
        Handles bankruptcy if the price drops to 0 or below.
        
        Args:
            symbol: The stock symbol to sell
            user_id: The ID of the user making the sale
            bot: Optional bot instance for bankruptcy handling
        
        Returns:
            Tuple of (sale price, was same day sale, was bankruptcy triggered)
        """
        # Get current price 
        base_price = cls.stock_prices[symbol]
        same_day_sale = False
        fee = 0
        bankruptcy_triggered = False
        
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
        new_price = cls.stock_prices[symbol] - change
        new_price = round(new_price, 2)
        
        # Check if this sale would trigger bankruptcy
        if new_price <= 0:
            logger.warning(f"Sale of {symbol} by user {user_id} triggered bankruptcy (price: {new_price})")
            bankruptcy_triggered = True
            
            # Process the bankruptcy
            affected_users = await cls.handle_bankruptcy(symbol, bot)
            
            # Send bankruptcy notification to terminal channel if bot is provided
            if bot:
                try:
                    terminal_channel = bot.get_channel(config.TERMINAL_CHANNEL_ID)
                    if terminal_channel:
                        embed = discord.Embed(
                            title=f"📉 Stock Bankruptcy: {symbol}",
                            description=f"**{symbol}** has gone bankrupt after a sale by <@{user_id}> and has been delisted from the exchange!",
                            color=config.COLOR_ERROR
                        )
                        
                        # Add information about affected users
                        if affected_users:
                            user_list = []
                            for affected_id, shares in affected_users:
                                try:
                                    user = await bot.fetch_user(int(affected_id))
                                    user_list.append(f"{user.mention}: Lost {shares} shares")
                                except:
                                    user_list.append(f"User {affected_id}: Lost {shares} shares")
                            
                            if user_list:
                                embed.add_field(
                                    name="Affected Investors",
                                    value="\n".join(user_list[:10]) + 
                                        (f"\n... and {len(user_list) - 10} more" if len(user_list) > 10 else ""),
                                    inline=False
                                )
                        
                        # Add footer
                        embed.set_footer(text="All shares have been removed and the stock has been delisted.")
                        
                        # Send announcement
                        await terminal_channel.send(embed=embed)
                        logger.info(f"Sent bankruptcy announcement for {symbol}")
                    else:
                        logger.error(f"Could not find terminal channel with ID {config.TERMINAL_CHANNEL_ID}")
                except Exception as e:
                    logger.error(f"Error sending bankruptcy notification: {e}", exc_info=True)
            
            # Return the sale price but don't update the stock data since it's being removed
            return sale_price, same_day_sale, bankruptcy_triggered
        
        # Normal case - update the stock data
        cls.stock_prices[symbol] = new_price
        cls.price_history[symbol].append(new_price)
        
        # Save changes
        cls.save_stocks()
        return sale_price, same_day_sale, bankruptcy_triggered
    
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
        ax.set_ylabel(f"{symbol} Price ({config.UOM})")
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
    async def handle_bankruptcy(cls, symbol, bot=None):
        """
        Handle a stock going bankrupt (price reaching 0 or below)
        - Remove stock from stored symbols
        - Delete stock screener message
        - Remove stock from all user inventories
        - Remove stock from internal tracking structures
        
        Args:
            symbol: The stock symbol that went bankrupt
            bot: Optional Discord bot instance to use for message deletion
        """
        logger.info(f"🔥 Stock {symbol} has gone bankrupt! Beginning bankruptcy process...")
        logger.info(f"Current price of {symbol}: ${cls.stock_prices.get(symbol, 'N/A')}")
        
        try:
            # Find associated user ID before deleting anything
            associated_user_id = None
            for user_id, ticker in list(cls.user_to_ticker.items()):
                if ticker == symbol:
                    associated_user_id = user_id
                    break
            
            logger.info(f"Associated user ID for {symbol}: {associated_user_id}")
            
            # 1. Delete the screener message if it exists
            if symbol in cls.stock_messages:
                logger.info(f"Attempting to delete screener message for {symbol}")
                message_id = cls.stock_messages[symbol]
                
                if bot:
                    # Use the provided bot instance
                    logger.info(f"Using provided bot instance to delete message")
                    channel = bot.get_channel(config.STOCK_CHANNEL_ID)
                    if channel:
                        try:
                            message = await channel.fetch_message(message_id)
                            await message.delete()
                            logger.info(f"Successfully deleted screener message for bankrupt stock {symbol}")
                        except discord.NotFound:
                            logger.warning(f"Screener message for {symbol} already deleted or not found")
                        except Exception as e:
                            logger.error(f"Error deleting screener message for {symbol}: {e}", exc_info=True)
                    else:
                        logger.error(f"Could not find stock channel with ID {config.STOCK_CHANNEL_ID}")
                else:
                    # Just log that we couldn't delete the message
                    logger.warning(f"No bot instance provided, skipping message deletion for {symbol} (ID: {message_id})")
                    
                # Remove from stock_messages dict regardless of whether deletion succeeded
                del cls.stock_messages[symbol]
                cls.save_stock_messages()
                logger.info(f"Removed {symbol} from stock_messages and saved")
            else:
                logger.info(f"No message ID found for {symbol} in stock_messages")
            
            # 2. Remove stock from all user inventories and purchase dates
            from data_manager import DataManager
            user_data = DataManager.load_data(config.USER_DATA_FILE)
            bankruptcy_announcement = []
            
            logger.info(f"Checking {len(user_data)} user records for {symbol} shares")
            affected_count = 0
            
            for user_id, data in user_data.items():
                # Clean up inventory
                if "inventory" in data and symbol in data["inventory"]:
                    # Record users who lost shares for announcement
                    shares_lost = data["inventory"][symbol]
                    bankruptcy_announcement.append((user_id, shares_lost))
                    affected_count += 1
                    
                    # Remove from inventory
                    del data["inventory"][symbol]
                    logger.info(f"Removed bankrupt stock {symbol} from user {user_id}'s inventory ({shares_lost} shares)")
                
                # Clean up purchase dates
                if "purchase_dates" in data and symbol in data["purchase_dates"]:
                    del data["purchase_dates"][symbol]
                    logger.info(f"Removed purchase dates for {symbol} from user {user_id}")
            
            logger.info(f"Found {affected_count} users affected by {symbol} bankruptcy")
            
            # Save updated user data
            DataManager.save_data(config.USER_DATA_FILE, user_data)
            logger.info(f"Saved updated user data after {symbol} bankruptcy")
            
            # 3. Remove from in-memory tracking
            if symbol in cls.stock_prices:
                del cls.stock_prices[symbol]
                logger.info(f"Removed {symbol} from stock_prices")
            
            if symbol in cls.price_history:
                del cls.price_history[symbol]
                logger.info(f"Removed {symbol} from price_history")
            
            # 4. Remove from stock_symbols list
            if symbol in cls.stock_symbols:
                cls.stock_symbols.remove(symbol)
                logger.info(f"Removed {symbol} from stock_symbols")
            else:
                logger.warning(f"{symbol} not found in stock_symbols")
            
            # 5. Remove from user_to_ticker mapping
            if associated_user_id:
                if associated_user_id in cls.user_to_ticker:
                    del cls.user_to_ticker[associated_user_id]
                    logger.info(f"Removed user {associated_user_id} association with {symbol} from user_to_ticker")
                else:
                    logger.warning(f"User {associated_user_id} not found in user_to_ticker dict")
            else:
                logger.warning(f"No user associated with {symbol} found in user_to_ticker")
            
            # 6. Save the updated data
            cls.save_stocks()
            logger.info(f"✅ Successfully completed bankruptcy process for {symbol}")
            
            # 7. Return bankruptcy announcement data for potential notification
            return bankruptcy_announcement
            
        except Exception as e:
            logger.error(f"Major error in bankruptcy handling for {symbol}: {e}", exc_info=True)
            # Attempt a simplified removal as a fallback
            try:
                if symbol in cls.stock_prices:
                    del cls.stock_prices[symbol]
                if symbol in cls.price_history:
                    del cls.price_history[symbol]
                if symbol in config.STOCK_SYMBOLS:
                    config.STOCK_SYMBOLS.remove(symbol)
                cls.save_stocks()
                logger.info(f"Performed simplified removal of {symbol} after error")
            except:
                logger.critical(f"Even simplified bankruptcy cleanup failed for {symbol}")
            
            return []
                
    @classmethod
    async def handle_emergency_bankruptcies(cls, bot=None):
        """
        Emergency method to immediately handle any stocks that are at or below 0 price
        
        Args:
            bot: Optional Discord bot instance to use for message deletion
        """
        logger.info("🚨 Performing emergency bankruptcy check on all stocks")
        
        # Check all stocks for negative values
        bankrupt_stocks = []
        for symbol, price in list(cls.stock_prices.items()):
            if price <= 0:
                logger.warning(f"Found stock {symbol} at price ${price} - flagging for emergency bankruptcy")
                bankrupt_stocks.append(symbol)
        
        if not bankrupt_stocks:
            logger.info("No stocks requiring bankruptcy found")
            return False
        
        # Handle each bankrupt stock
        bankruptcy_announcements = {}
        for symbol in bankrupt_stocks:
            try:
                announcement_data = await cls.handle_bankruptcy(symbol, bot)
                bankruptcy_announcements[symbol] = announcement_data
                logger.warning(f"Emergency bankruptcy processed for {symbol}")
            except Exception as e:
                logger.error(f"Error handling emergency bankruptcy for {symbol}: {e}", exc_info=True)
        
        # Handle announcements if bot was provided
        if bot and bankruptcy_announcements:
            try:
                # Use TERMINAL_CHANNEL_ID instead of STOCK_CHANNEL_ID
                channel = bot.get_channel(config.TERMINAL_CHANNEL_ID)
                if channel:
                    for symbol, affected_users in bankruptcy_announcements.items():
                        embed = discord.Embed(
                            title=f"📉 Emergency Delisting: {symbol}",
                            description=f"**{symbol}** has been forcibly delisted from the exchange due to bankruptcy!",
                            color=config.COLOR_ERROR
                        )
                        
                        if affected_users:
                            user_list = []
                            for user_id, shares in affected_users:
                                try:
                                    user = await bot.fetch_user(int(user_id))
                                    user_list.append(f"{user.mention}: Lost {shares} shares")
                                except:
                                    user_list.append(f"User {user_id}: Lost {shares} shares")
                            
                            if user_list:
                                embed.add_field(
                                    name="Affected Investors",
                                    value="\n".join(user_list[:10]) + 
                                        (f"\n... and {len(user_list) - 10} more" if len(user_list) > 10 else ""),
                                    inline=False
                                )
                        
                        embed.set_footer(text="All shares have been removed and the stock has been delisted.")
                        
                        try:
                            await channel.send(embed=embed)
                            logger.info(f"Sent emergency bankruptcy announcement for {symbol}")
                        except Exception as e:
                            logger.error(f"Error sending bankruptcy announcement for {symbol}: {e}")
                else:
                    logger.error(f"Terminal channel with ID {config.TERMINAL_CHANNEL_ID} not found")
            except Exception as e:
                logger.error(f"Error while trying to announce bankruptcies: {e}", exc_info=True)
        
        return True

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