"""
Commands module for CH3F Exchange Discord Bot
"""
import random
import logging
from datetime import datetime, timezone
import pytz
import asyncio

import discord
from discord.ext import commands

import config
import admin_commands
from utils import create_stock_screener
from data_manager import DataManager
from user_manager import UserManager
from stock_manager import StockManager
from ui_components import ChartView, HelpView, BalanceLeaderboardView, StockLeaderboardView

logger = logging.getLogger('ch3f_exchange.commands')

# Export the process_command function at the module level
__all__ = ['process_command', 'setup']

def balance(ctx):
    """Check your balance command"""
    DataManager.ensure_user(ctx.author.id)
    bal = UserManager.get_balance(ctx.author.id)
    bank_amt = UserManager.get_bank(ctx.author.id)
    
    embed = discord.Embed(
        title="💰 Balance",
        description=f"Your balance: **${bal:.2f} CCD**",
        color=config.COLOR_INFO
    )
    
    if bank_amt > 0:
        embed.add_field(name="Bank Balance", value=f"**${bank_amt:.2f} CCD**")
    
    return embed

def daily(ctx):
    """Claim daily reward command"""
    data = DataManager.ensure_user(ctx.author.id)
    user_id = str(ctx.author.id)
    utc_now = datetime.now(pytz.utc)
    eastern = pytz.timezone("America/New_York")
    est_now = utc_now.astimezone(eastern)
    today = est_now.strftime("%Y-%m-%d")
    last_claimed = data[user_id].get("last_daily", None)
    
    if last_claimed == today:
        return f"⚠️ {ctx.author.mention}, you have already claimed your daily reward today!"
    
    # Generate random daily reward
    reward = round(random.uniform(config.DAILY_REWARD_MIN, config.DAILY_REWARD_MAX), 2)
    data[user_id]["balance"] += reward
    data[user_id]["last_daily"] = today
    
    DataManager.save_data(config.USER_DATA_FILE, data)
    
    embed = discord.Embed(
        title="🎁 Daily Reward",
        description=f"You claimed your daily **${reward:.2f} CCD**!",
        color=config.COLOR_WARNING
    )
    
    return embed

def gift(ctx, user, amount):
    """Gift CCD to another user"""
    # Validate input
    if amount <= 0:
        return "⚠️ Invalid amount. Please enter a positive number."
    
    # Ensure both users exist in database
    DataManager.ensure_user(ctx.author.id)
    DataManager.ensure_user(user.id)
    
    # Check balance
    bal = UserManager.get_balance(ctx.author.id)
    if bal < amount:
        return "❌ You don't have enough $CCD for this gift."
    
    # Transfer the amount
    UserManager.update_balance(ctx.author.id, -amount)
    UserManager.update_balance(user.id, amount)
    
    # Send confirmation
    embed = discord.Embed(
        title="🎁 Gift Sent",
        description=f"You gifted **${amount:.2f} CCD** to {user.mention}!",
        color=config.COLOR_SPECIAL
    )
    
    return embed

def leaderboard(ctx, bot):
    """Show balance leaderboard"""
    channel = bot.get_channel(config.LEADERBOARD_CHANNEL_ID)
    if channel and channel.id != ctx.channel.id:
        return f"📊 Check out the leaderboards in {channel.mention}!"
    else:
        # Show inline leaderboard
        view = BalanceLeaderboardView()
        return view.get_embed(ctx.guild)

def stocks(ctx, bot):
    """Show stock leaderboard"""
    channel = bot.get_channel(config.STOCK_CHANNEL_ID)
    if channel and channel.id != ctx.channel.id:
        return f"📊 Check out the stock market in {channel.mention}!"
    else:
        # Show inline leaderboard
        view = StockLeaderboardView()
        return view.get_embed()

def mystocks(ctx):
    """View your stock portfolio"""
    DataManager.ensure_user(ctx.author.id)
    inv = UserManager.user_inventory(ctx.author.id)
    
    if not inv:
        return "📉 You have no stocks in your portfolio."
    
    # Calculate portfolio value
    total_value = 0
    desc = ""
    
    for stock, quantity in inv.items():
        if stock in StockManager.stock_prices:
            value = StockManager.stock_prices[stock] * quantity
            total_value += value
            desc += f"{stock}: **x{quantity}** (${value:.2f} CCD)\n"
        else:
            desc += f"{stock}: **x{quantity}** (Unknown value)\n"
    
    # Create embed
    embed = discord.Embed(
        title="📊 Your Stock Portfolio",
        description=desc,
        color=config.COLOR_INFO
    )
    
    embed.add_field(
        name="Total Portfolio Value",
        value=f"**${total_value:.2f} CCD**"
    )
    
    return embed

async def stock_command(ctx, symbol, bot):
    """Display information about a specific stock"""
    # Make sure symbol has $ prefix and is uppercase
    symbol = symbol.upper()
    if not symbol.startswith('$'):
        symbol = f"${symbol}"
    
    if symbol not in config.STOCK_SYMBOLS:
        return f"⚠️ Unknown stock symbol: {symbol}"
    
    # Create stock chart view
    view = ChartView(symbol)
    file, embed = await view.get_embed()
    
    # Send message with chart
    message = await ctx.channel.send(embed=embed, file=file, view=view)
    view.message = message
    return None

async def create_stock(ctx, symbol, bot=None):
    """Create a new stock (IPO) for a user"""
    # Validate input
    if not symbol:
        return "⚠️ Please provide a valid stock symbol. Example: !createstock XYZ"
    
    # Format symbol properly
    symbol = symbol.upper()
    if not symbol.startswith('$'):
        symbol = f"${symbol}"
    
    # Validate symbol format - alphanumeric, 2-4 characters (not including $)
    import re
    if not re.match(r'^\$[A-Z0-9]{2,4}$', symbol):
        return "⚠️ Stock symbol must be 2-4 alphanumeric characters. Example: $XYZ"
    
    # Check if user already has a stock
    user_id = str(ctx.author.id)
    
    # Use StockManager to check if user already has a stock
    user_stock = StockManager.get_user_stock(user_id)
    if user_stock:
        return f"⚠️ You already have a stock: {user_stock}"
    
    # Check if symbol already exists
    if symbol in StockManager.get_all_symbols():
        return f"⚠️ Stock symbol {symbol} already exists. Please choose another."
        
    # Check if user has enough funds
    DataManager.ensure_user(ctx.author.id)
    bal = UserManager.get_balance(ctx.author.id)
        
    if bal < config.IPO_COST:
        return f"❌ Insufficient funds. Creating a stock costs ${config.IPO_COST} CCD. You have ${bal:.2f} CCD."
        
    # Charge the user
    UserManager.update_balance(ctx.author.id, -config.IPO_COST)
    
    # Add stock to the system via StockManager
    success = await StockManager.add_stock(symbol, user_id)
    
    if not success:
        # Refund the user if there was an error
        UserManager.update_balance(ctx.author.id, config.IPO_COST)
        return "❌ There was an error creating your stock. Please try again."
    
    # Create stock screener message
    asyncio.create_task(create_stock_screener(ctx, symbol, bot))
    
    # Create success message
    embed = discord.Embed(
        title="🚀 Stock Created Successfully!",
        description=f"Congratulations {ctx.author.mention}! You've successfully created **{symbol}** stock.\nStarting price: **${StockManager.stock_prices[symbol]:.2f} CCD**",
        color=config.COLOR_SUCCESS
    )
    
    embed.add_field(
        name="Next Steps",
        value="Your stock will now appear in the stock channel and participate in market updates."
    )
    
    return embed

def about(ctx):
    """Display information about the bot"""
    embed = discord.Embed(
        title="About The CH3F Exchange",
        description="This is a bot built to simulate the CH3F Clan Stock Exchange.",
        color=config.COLOR_DISCORD
    )
    
    embed.add_field(
        name="Creator",
        value="Created by Gage Johnson."
    )
    
    embed.add_field(
        name="Features",
        value="• Virtual currency ($CCD)\n• Stock market simulation\n• Interactive commands\n• Reaction rewards"
    )
    
    embed.add_field(
        name="Commands",
        value="Type `!help` to see all available commands."
    )
    
    return embed

def help(ctx):
    """Display command list"""
    view = HelpView()
    return view.get_embed()



async def process_command(bot, message):
    """Process commands from messages"""
    if message.author.bot:
        return False
    
    if not message.content.startswith('!'):
        return False
    
    parts = message.content.split()
    command = parts[0][1:].lower()
    args = parts[1:]
    
    logger.info(f"Processing command: {command} with args: {args}")
    
    ctx = message
    try:
        if command in ['balance', 'bal']:
            return balance(ctx)
        
        elif command == 'daily':
            return daily(ctx)
        
        elif command == 'gift':
            if len(args) < 2:
                return "Usage: !gift @user amount"
            try:
                # Get user from mention
                if message.mentions:
                    user = message.mentions[0]
                else:
                    user_id = args[0].strip('<@!>')
                    if not user_id.isdigit():
                        return "Please mention a user to gift CCD to."
                    user = bot.get_user(int(user_id)) or await bot.fetch_user(int(user_id))
                
                amount = float(args[1])
                return gift(ctx, user, amount)
            except (ValueError, IndexError) as e:
                logger.error(f"Error in gift command: {e}")
                return "Invalid amount. Please use the format: !gift @user amount"
        
        elif command == 'leaderboard':
            return leaderboard(ctx, bot)
        
        elif command in ['stocks', 'stockmarket']:
            return stocks(ctx, bot)
        
        elif command in ['mystocks', 'portfolio', 'port']:
            return mystocks(ctx)
        
        elif command in ['createstock', 'ipo']:
            if len(args) < 1:
                return "Please specify a stock symbol. Example: !createstock XYZ"
            return await create_stock(ctx, args[0], bot)
        
        elif command == 'about':
            return about(ctx)
        
        elif command == 'help':
            return help(ctx)
        
        # Admin commands
        elif command == 'admin_add':
            if len(args) < 2:
                return "Usage: !admin_add <@user or ticker> <amount>"
            return await admin_commands.admin_add(ctx, args[0], args[1], bot)
        
        elif command == 'admin_sub':
            if len(args) < 2:
                return "Usage: !admin_sub <@user or ticker> <amount>"
            return await admin_commands.admin_sub(ctx, args[0], args[1], bot)
        
        elif command == 'admin_bankrupt':
            if len(args) < 1:
                return "Usage: !admin_bankrupt <@user or ticker>"
            return await admin_commands.admin_bankrupt(ctx, args[0], bot)
        

        elif command == 'admin_set':
            if len(args) < 2:
                return "Usage: !admin_set <@user or ticker> <amount>"
            return await admin_commands.admin_set(ctx, args[0], args[1], bot)
        
        elif command == 'admin_gift':
            if len(args) < 2:
                return "Usage: !admin_gift <@user> <amount>"
            return await admin_commands.admin_gift(ctx, args[0], args[1], bot)
        
        elif command == 'admin_create_stock':
            if len(args) < 1:
                return "Usage: !admin_create_stock <symbol> [initial_price] [@user]"
            
            initial_price = None
            user = None
            
            if len(args) > 1:
                # Check if second arg is a price or user
                if args[1].startswith('<@'):
                    user = args[1]
                else:
                    try:
                        initial_price = args[1]
                        if len(args) > 2:
                            user = args[2]
                    except ValueError:
                        return "⚠️ Invalid initial price. Please enter a valid number."
            
            return await admin_commands.admin_create_stock(ctx, args[0], initial_price, user, bot)
        
        elif command == 'admin_remove_stock':
            if len(args) < 1:
                return "Usage: !admin_remove_stock <symbol>"
            return await admin_commands.admin_remove_stock(ctx, args[0], bot)
        
        elif command == 'admin_market':
            condition = args[0] if args else None
            return await admin_commands.admin_market_condition(ctx, condition, bot)
        
        elif command == 'admin_award_all':
            if len(args) < 1:
                return "Usage: !admin_award_all <amount>"
            return await admin_commands.admin_award_all(ctx, args[0], bot)
        
        elif command == 'admin_force_update':
            return await admin_commands.admin_force_update(ctx, bot)
            
        elif command == 'admin_help':
            return await admin_commands.admin_help(ctx, bot)
            
    except Exception as e:
        logger.error(f"Error processing command {command}: {e}", exc_info=True)
        return f"An error occurred: {str(e)}"
    
    return False

def setup(bot):
    """Setup commands"""
    logger.info("Setting up command processor")
    return True