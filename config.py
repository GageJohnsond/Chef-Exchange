"""
Configuration file for the CH3F Exchange Discord Bot
Contains all constant values, settings, and configurations
"""
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Bot token from environment variables
TOKEN = os.getenv("DISCORD_BOT_TOKEN")

#Admin User ID's
ADMIN_USER_IDS = [126535729156194304]

# Channel IDs
ACTIVE_CHANNEL_IDS = [707325634887548950, 1346629041066741843, 996963554039173131, 1342937283611070556]
STOCK_CHANNEL_ID = 1347399173221257227
LEADERBOARD_CHANNEL_ID = 1347399218175676536
TERMINAL_CHANNEL_ID = 1346629041066741843

# Economy settings
DAILY_CAP = 60
DAILY_REWARD_MIN = 15
DAILY_REWARD_MAX = 100
SELLING_FEE = 7  # Fee to sell stocks

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
STOCK_SYMBOLS = [
    "$SHNE", "$KORD", "$SPLY", "$KID", "$DREW", "$TRAX", "$DAR", 
    "$TOST", "$TAL", "$GAGE", "$SEVK", "$NINJ", "$YOLO", 
    "$LOOK", "$WAMR", "$RDGE"
]

# Mapping of user IDs to their ticker symbols
USER_TO_TICKER = {
    "489853259130077185": "$SHNE", "160980489719644161": "$KORD",
    "226124570233536533": "$SPLY", "289601944346034176": "$KID",
    "103233630515531776": "$DREW", "284075942014484480": "$TRAX",
    "709565709696368671": "$DAR", "709565709696368671": "$TOST",
    "325803101007380483": "$TAL", "126535729156194304": "$GAGE",
    "388455185468620820": "$SEVK", "1180393064997605436": "$NINJ",
    "694651316986707988": "$YOLO", "537008849987698688": "$LOOK",
    "356895872853999621": "$WAMR", "221986056193441792": "$RDGE"
}

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

# Command list for help 
COMMANDS = {
    "Economy": [
        ("!balance or !bal", "Check your $CCD balance"),
        ("!daily", "Claim daily reward"),
        ("!gift <@user> <amount>", "Gift $CCD to another user")
    ],
    "Stocks": [
        ("!portfolio or !port", "View your stock portfolio"),
        ("!createstock or !ipo <symbol>", "Create your own stock (costs $1000 CCD)")
    ],
    "Info": [
        ("!about", "About this bot"),
        ("!help", "Show this command menu")
    ]
}

# Default user data
DEFAULT_USER_DATA = {
    "balance": 50,
    "inventory": {},
    "last_daily": None,
    "bank": 0,
    "date": None,
    "earned": 0
}