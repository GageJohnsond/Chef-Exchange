"""
Commands module for CH3F Exchange Discord Bot
Contains all bot command definitions
"""
import random
import logging
from datetime import datetime, timezone
import pytz

import discord
from discord.ext import commands

import config
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

def about(ctx):
    """Display information about the bot"""
    embed = discord.Embed(
        title="About The CH3F Exchange",
        description="This is a bot built to simulate the CH3F Clan Stock Exchange.",
        color=config.COLOR_DISCORD
    )
    
    embed.add_field(
        name="Creator",
        value="Created by Gage"
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
        
        elif command in ['mystocks', 'portfolio']:
            return mystocks(ctx)
        
        elif command == 'stock':
            if len(args) < 1:
                return "Please specify a stock symbol. Example: !stock SHNE"
            await stock_command(ctx, args[0], bot)
            return None  # This command handles its own response
        
        elif command == 'about':
            return about(ctx)
        
        elif command == 'help':
            return help(ctx)
        
        else:
            return f"⚠️ {message.author.mention}, invalid command. See !help"
    
    except Exception as e:
        logger.error(f"Error processing command {command}: {e}", exc_info=True)
        return f"An error occurred: {str(e)}"
    
    return False

def setup(bot):
    """Setup commands"""
    logger.info("Setting up command processor")
    # No cogs needed anymore - we're using a custom command processor
    return True