"""
Stock management module for CH3F Exchange Discord Bot
Handles stock data, charts, and market operations
"""
import json
import random
import logging
from typing import Dict, Any

import matplotlib.pyplot as plt
import matplotlib.image as mpimg
from io import BytesIO

import config

logger = logging.getLogger('ch3f_exchange.stocks')

class StockManager:
    """Class to handle stock-related operations"""
    
    # Global stock data
    stock_prices = {}
    price_history = {}
    stock_messages = {}
    
    @classmethod
    def load_stocks(cls) -> Dict:
        """Load stock data from file or generate new stocks if needed"""
        try:
            with open(config.STOCKS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            if isinstance(data, dict) and "STOCK_PRICES" in data and "PRICE_HISTORY" in data:
                logger.info("✅ Loaded existing stock data.")
                cls.stock_prices = data["STOCK_PRICES"]
                cls.price_history = data["PRICE_HISTORY"]
                return data
            else:
                logger.warning("⚠️ stocks.json is missing required fields. Regenerating stock data...")
        
        except (json.JSONDecodeError, IOError, FileNotFoundError):
            logger.error("❌ Error: stocks.json is missing or corrupted. Regenerating stock data...")
        
        return cls.generate_new_stocks()
    
    @classmethod
    def save_stocks(cls) -> None:
        """Save stock data to file"""
        data = {
            "STOCK_PRICES": cls.stock_prices,
            "PRICE_HISTORY": cls.price_history
        }
        
        try:
            with open(config.STOCKS_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
            logger.info("💾 Stock data saved successfully.")
        except Exception as e:
            logger.error(f"Error saving stock data: {e}")
    
    @classmethod
    def generate_new_stocks(cls) -> Dict:
        """Generate new stock data"""
        stock_prices = {symbol: round(random.uniform(
            config.NEW_STOCK_MIN_PRICE, 
            config.NEW_STOCK_MAX_PRICE), 2) 
            for symbol in config.STOCK_SYMBOLS}
            
        price_history = {symbol: [stock_prices[symbol]] for symbol in config.STOCK_SYMBOLS}
        
        data = {
            "STOCK_PRICES": stock_prices,
            "PRICE_HISTORY": price_history
        }
        
        cls.stock_prices = stock_prices
        cls.price_history = price_history
        
        try:
            with open(config.STOCKS_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
            logger.info("🔄 New stock data generated and saved to stocks.json.")
        except Exception as e:
            logger.error(f"Error saving new stock data: {e}")
            
        return data
    
    @classmethod
    def load_stock_messages(cls) -> Dict:
        """Load stock message IDs from file"""
        if not cls.stock_messages:  # Only load if not already loaded
            if open(config.STOCK_MESSAGES_FILE, "a").close() or True:  # Create file if it doesn't exist
                try:
                    with open(config.STOCK_MESSAGES_FILE, "r", encoding="utf-8") as f:
                        cls.stock_messages = json.load(f)
                        logger.info("Loaded stock message IDs.")
                except json.JSONDecodeError:
                    logger.warning("⚠️ stocks_messages.json is corrupted. Resetting...")
                    cls.stock_messages = {}
                except FileNotFoundError:
                    logger.info("Creating new stocks_messages.json file.")
                    cls.stock_messages = {}
        
        return cls.stock_messages
    
    @classmethod
    def save_stock_messages(cls) -> None:
        """Save stock message IDs to file"""
        try:
            with open(config.STOCK_MESSAGES_FILE, "w", encoding="utf-8") as f:
                json.dump(cls.stock_messages, f, indent=4)
            logger.info("Stock message IDs saved.")
        except Exception as e:
            logger.error(f"Error saving stock message IDs: {e}")
    
    @classmethod
    def update_prices(cls) -> None:
        """Update stock prices with random changes"""
        for symbol in config.STOCK_SYMBOLS:
            change = random.uniform(config.STOCK_PRICE_MIN_CHANGE, config.STOCK_PRICE_MAX_CHANGE)
            new_price = max(1, cls.stock_prices[symbol] + change)
            cls.stock_prices[symbol] = round(new_price, 2)
            cls.price_history[symbol].append(round(new_price, 2))
        
        cls.save_stocks()
    
    @classmethod
    def buy_stock(cls, symbol: str) -> float:
        """Process a stock purchase and update prices"""
        price = cls.stock_prices[symbol]
        
        # Increase stock price after purchase
        change = random.uniform(config.STOCK_BUY_MIN_CHANGE, config.STOCK_BUY_MAX_CHANGE)
        new_price = max(1, cls.stock_prices[symbol] + change)
        cls.stock_prices[symbol] = round(new_price, 2)
        cls.price_history[symbol].append(round(new_price, 2))
        
        cls.save_stocks()
        return price
    
    @classmethod
    def sell_stock(cls, symbol: str) -> float:
        """Process a stock sale and update prices"""
        price = cls.stock_prices[symbol] - config.SELLING_FEE  # Apply selling fee
        
        # Decrease stock price after sale
        change = random.uniform(config.STOCK_SELL_MIN_CHANGE, config.STOCK_SELL_MAX_CHANGE)
        new_price = max(1, cls.stock_prices[symbol] - change)
        cls.stock_prices[symbol] = round(new_price, 2)
        cls.price_history[symbol].append(round(new_price, 2))
        
        cls.save_stocks()
        return price
    
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
            
        ax.plot(x_values, history, marker='o', color=color, linestyle='-')
        
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