"""
Configuration file for the Stock Exchange Discord Bot
Contains all constant values, settings, and configurations
"""
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Bot token from environment variables
TOKEN = os.getenv("DISCORD_BOT_TOKEN")

#Exchange Name
NAME = "CH3F" #Name of the Exchange eg: The <NAME> Exchange

#Admin User ID's
ADMIN_USER_IDS = [126535729156194304]

# Channel IDs
ACTIVE_CHANNEL_IDS = [707325634887548950, 1346629041066741843, 996963554039173131, 1342937283611070556]
STOCK_CHANNEL_ID = 1347399173221257227
LEADERBOARD_CHANNEL_ID = 1347399218175676536
TERMINAL_CHANNEL_ID = 1346629041066741843

# Economy settings
UOM="CCD"
DAILY_CAP = 60
DAILY_REWARD_MIN = 15
DAILY_REWARD_MAX = 100
SELLING_FEE = 7  # Fee to sell stocks
REBRAND_FEE = 500 #Fee to rename stock

# Dividend settings
TOP_SHAREHOLDERS_COUNT = 3  # Number of top shareholders to reward
CREATOR_DIVIDEND_PERCENT = 2  # Percentage of stock price per shareholder
TOP_SHAREHOLDER_DIVIDENDS = {
    0: 15,  # 15% of stock price to top shareholder
    1: 10,  # 10% of stock price to second place
    2: 5  # 5% of stock price to third place
}

# Stock decay settings
STOCK_DECAY_THRESHOLD = 15  # Maximum number of stocks before decay starts
STOCK_DECAY_PERCENT = 3.0   # Percentage to reduce price by on each update
STOCK_BANKRUPTCY_THRESHOLD = 5.0  # Price threshold for bankruptcy warning

# Message rewards
MESSAGE_REWARD_MIN = 1
MESSAGE_REWARD_MAX = 3
REACTION_REWARD_AUTHOR_MIN = 2
REACTION_REWARD_AUTHOR_MAX = 5
REACTION_REWARD_REACTOR_MIN = 1
REACTION_REWARD_REACTOR_MAX = 2

# File paths
USER_DATA_FILE = "user_data.json"
STOCKS_FILE = "stocks.json"
STOCK_MESSAGES_FILE = "stocks_messages.json"
LEADERBOARD_MESSAGES_FILE = "leaderboard_messages.json"
LOGO_FILE = "logo.png"

# Stock configuration
IPO_COST = 1000

# Update settings
STOCK_UPDATE_INTERVAL = 45  # minutes
LEADERBOARD_UPDATE_INTERVAL = 15  # minutes
STOCK_PRICE_MIN_CHANGE = -3
STOCK_PRICE_MAX_CHANGE = 3
NEW_STOCK_MIN_PRICE = 80
NEW_STOCK_MAX_PRICE = 90
STOCK_BUY_MIN_CHANGE = 3
STOCK_BUY_MAX_CHANGE = 9
STOCK_SELL_MIN_CHANGE = 3
STOCK_SELL_MAX_CHANGE = 9

# Colors
COLOR_SUCCESS = 0x00FF00  # Green
COLOR_ERROR = 0xFF0000  # Red
COLOR_INFO = 0x3498DB  # Blue
COLOR_WARNING = 0xFFD700  # Gold
COLOR_SPECIAL = 0xE91E63  # Pink
COLOR_DISCORD = 0x7289DA  # Discord Blurple


# Default user data
DEFAULT_USER_DATA = {
    "balance": 1250,
    "inventory": {},
    "last_daily": None,
    "bank": 0,
    "date": None,
    "earned": 0
}