"""
Commands module for CH3F Exchange Discord Bot
Contains all bot command definitions
"""
import random
import logging
from datetime import datetime, timezone
import pytz
import asyncio

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

async def create_stock_screener(ctx, symbol, bot=None):
    """Create a stock screener message for the new stock"""
    # Get stock channel
    if bot is None:
        # This is a fallback, but we should pass bot from process_command
        from main import create_bot
        bot = create_bot()
        await bot.login(config.TOKEN)
    
    channel = bot.get_channel(config.STOCK_CHANNEL_ID)
    if not channel:
        logger.error(f"Failed to create stock screener for {symbol}: Stock channel not found")
        return
    
    # Create and send chart
    view = ChartView(symbol)
    file, embed = await view.get_embed()
    
    try:
        message = await channel.send(embed=embed, file=file, view=view)
        StockManager.stock_messages[symbol] = message.id
        view.message = message
        logger.info(f"Created stock screener for {symbol}")
        
        # Save message IDs
        StockManager.save_stock_messages()
    except Exception as e:
        logger.error(f"Error creating stock screener for {symbol}: {e}")

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

async def admin_add(ctx, target, amount, bot=None):
    """Admin command to add value to a stock"""
    # Security check - only allow specific admin users
    if ctx.author.id not in config.ADMIN_USER_IDS:
        return "❌ You don't have permission to use admin commands."

    # Parse amount
    try:
        amount_value = float(amount)
        if amount_value <= 0:
            return "⚠️ Please provide a positive number for the amount."
    except ValueError:
        return "⚠️ Invalid amount. Please enter a valid number."

    # Determine target stock symbol
    symbol = None
    
    # If target starts with @, it's a user mention
    if target.startswith('<@') and target.endswith('>'):
        # Extract user ID from mention
        user_id = target.strip('<@!>')
        
        # Check if the user has an associated stock
        if user_id.isdigit():
            user_id = str(user_id)
            symbol = StockManager.get_user_stock(user_id)
            if not symbol:
                return f"⚠️ No stock found for user {target}."
    else:
        # Check if it's a ticker symbol
        target_symbol = target.upper()
        if not target_symbol.startswith('$'):
            target_symbol = f"${target_symbol}"
        
        # Check if the symbol exists
        if target_symbol in StockManager.get_all_symbols():
            symbol = target_symbol
        else:
            return f"⚠️ Stock symbol {target_symbol} not found."
    
    # Update the stock price
    current_price = StockManager.stock_prices[symbol]
    new_price = current_price + amount_value
    
    # Ensure price doesn't go below 0
    if new_price <= 0:
        return f"⚠️ Cannot adjust price below $0. Current price is ${current_price:.2f}"
    
    # Update the price
    StockManager.stock_prices[symbol] = round(new_price, 2)
    
    # Add to price history
    StockManager.price_history[symbol].append(round(new_price, 2))
    
    # Save changes
    StockManager.save_stocks()
    
    # Create a response embed
    embed = discord.Embed(
        title="🔧 Admin: Stock Price Adjusted",
        description=f"Added **${amount_value:.2f}** to **{symbol}**",
        color=config.COLOR_WARNING
    )
    
    embed.add_field(
        name="Previous Price",
        value=f"${current_price:.2f}",
        inline=True
    )
    
    embed.add_field(
        name="New Price",
        value=f"${new_price:.2f}",
        inline=True
    )
    
    embed.add_field(
        name="Change",
        value=f"+${amount_value:.2f} (+{(amount_value/current_price)*100:.1f}%)",
        inline=True
    )
    
    # Try to update the stock's message if it exists
    if bot:
        channel = bot.get_channel(config.STOCK_CHANNEL_ID)
        if channel and symbol in StockManager.stock_messages:
            try:
                message_id = StockManager.stock_messages[symbol]
                message = await channel.fetch_message(message_id)
                
                # Create a new chart view
                view = ChartView(symbol)
                view.message = message
                await view.update_chart()
                logger.info(f"Updated chart for {symbol} after admin price adjustment")
            except Exception as e:
                logger.error(f"Error updating chart for {symbol}: {e}")
    
    return embed


async def admin_sub(ctx, target, amount, bot=None):
    """Admin command to subtract value from a stock"""
    # Security check - only allow specific admin users
    if ctx.author.id not in config.ADMIN_USER_IDS:
        return "❌ You don't have permission to use admin commands."

    # Parse amount
    try:
        amount_value = float(amount)
        if amount_value <= 0:
            return "⚠️ Please provide a positive number for the amount."
    except ValueError:
        return "⚠️ Invalid amount. Please enter a valid number."

    # Determine target stock symbol
    symbol = None
    
    # If target starts with @, it's a user mention
    if target.startswith('<@') and target.endswith('>'):
        # Extract user ID from mention
        user_id = target.strip('<@!>')
        
        # Check if the user has an associated stock
        if user_id.isdigit():
            user_id = str(user_id)
            symbol = StockManager.get_user_stock(user_id)
            if not symbol:
                return f"⚠️ No stock found for user {target}."
    else:
        # Check if it's a ticker symbol
        target_symbol = target.upper()
        if not target_symbol.startswith('$'):
            target_symbol = f"${target_symbol}"
        
        # Check if the symbol exists
        if target_symbol in StockManager.get_all_symbols():
            symbol = target_symbol
        else:
            return f"⚠️ Stock symbol {target_symbol} not found."
    
    # Update the stock price
    current_price = StockManager.stock_prices[symbol]
    new_price = current_price - amount_value
    
    # Check if this would cause bankruptcy
    if new_price <= 0:
        return (f"⚠️ This adjustment would cause {symbol} to go bankrupt (price would be ${new_price:.2f}). "
                f"If you want to bankrupt this stock, use the `!admin_bankrupt` command instead.")
    
    # Update the price
    StockManager.stock_prices[symbol] = round(new_price, 2)
    
    # Add to price history
    StockManager.price_history[symbol].append(round(new_price, 2))
    
    # Save changes
    StockManager.save_stocks()
    
    # Create a response embed
    embed = discord.Embed(
        title="🔧 Admin: Stock Price Adjusted",
        description=f"Subtracted **${amount_value:.2f}** from **{symbol}**",
        color=config.COLOR_WARNING
    )
    
    embed.add_field(
        name="Previous Price",
        value=f"${current_price:.2f}",
        inline=True
    )
    
    embed.add_field(
        name="New Price",
        value=f"${new_price:.2f}",
        inline=True
    )
    
    embed.add_field(
        name="Change",
        value=f"-${amount_value:.2f} (-{(amount_value/current_price)*100:.1f}%)",
        inline=True
    )
    
    # Try to update the stock's message if it exists
    if bot:
        channel = bot.get_channel(config.STOCK_CHANNEL_ID)
        if channel and symbol in StockManager.stock_messages:
            try:
                message_id = StockManager.stock_messages[symbol]
                message = await channel.fetch_message(message_id)
                
                # Create a new chart view
                view = ChartView(symbol)
                view.message = message
                await view.update_chart()
                logger.info(f"Updated chart for {symbol} after admin price adjustment")
            except Exception as e:
                logger.error(f"Error updating chart for {symbol}: {e}")
    
    return embed

async def admin_bankrupt(ctx, target, bot=None):
    """Admin command to force a stock bankruptcy"""
    # Security check - only allow specific admin users
    if ctx.author.id not in config.ADMIN_USER_IDS:
        return "❌ You don't have permission to use admin commands."

    # Determine target stock symbol
    symbol = None
    
    # If target starts with @, it's a user mention
    if target.startswith('<@') and target.endswith('>'):
        # Extract user ID from mention
        user_id = target.strip('<@!>')
        
        # Check if the user has an associated stock
        if user_id.isdigit():
            user_id = str(user_id)
            symbol = StockManager.get_user_stock(user_id)
            if not symbol:
                return f"⚠️ No stock found for user {target}."
    else:
        # Check if it's a ticker symbol
        target_symbol = target.upper()
        if not target_symbol.startswith('$'):
            target_symbol = f"${target_symbol}"
        
        # Check if the symbol exists
        if target_symbol in StockManager.get_all_symbols():
            symbol = target_symbol
        else:
            return f"⚠️ Stock symbol {target_symbol} not found."
    
    # Create confirmation message
    embed = discord.Embed(
        title="⚠️ BANKRUPTCY CONFIRMATION",
        description=f"Are you sure you want to force **{symbol}** into bankruptcy?\n\nThis will:\n- Remove the stock from the exchange\n- Delete all shares from user inventories\n- This action cannot be undone",
        color=config.COLOR_ERROR
    )
    
    # Create confirm/cancel buttons
    class BankruptConfirmView(discord.ui.View):
        def __init__(self, symbol, bot, original_user):
            super().__init__(timeout=60)
            self.symbol = symbol
            self.bot = bot
            self.original_user = original_user
        
        @discord.ui.button(label="Confirm Bankruptcy", style=discord.ButtonStyle.danger)
        async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
            # Check that only the original user can confirm
            if interaction.user.id != self.original_user.id:
                await interaction.response.send_message("Only the user who initiated this command can confirm it.", ephemeral=True)
                return
            
            # Set price to 0 to trigger bankruptcy
            StockManager.stock_prices[self.symbol] = 0
            
            # Process the bankruptcy
            announcement_data = await StockManager.handle_bankruptcy(self.symbol, bot)
            
            # Create response
            response_embed = discord.Embed(
                title="💥 BANKRUPTCY EXECUTED",
                description=f"**{self.symbol}** has been forced into bankruptcy and removed from the exchange.",
                color=config.COLOR_ERROR
            )
            
            # Add info about affected users
            if announcement_data:
                affected_count = len(announcement_data)
                response_embed.add_field(
                    name="Affected Users",
                    value=f"{affected_count} users lost their shares of {self.symbol}.",
                    inline=False
                )
            
            await interaction.response.edit_message(embed=response_embed, view=None)
        
        @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
        async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
            await interaction.response.edit_message(
                embed=discord.Embed(
                    title="Action Cancelled",
                    description="Bankruptcy process has been cancelled.",
                    color=config.COLOR_INFO
                ),
                view=None
            )
    
    # Send the confirmation message with buttons
    view = BankruptConfirmView(symbol, bot, ctx.author)
    message = await ctx.channel.send(embed=embed, view=view)
    
    # Return None because we've already sent our own message
    return None

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
            return await admin_add(ctx, args[0], args[1], bot)
        
        elif command == 'admin_sub':
            if len(args) < 2:
                return "Usage: !admin_sub <@user or ticker> <amount>"
            return await admin_sub(ctx, args[0], args[1], bot)
        
        elif command == 'admin_bankrupt':
            if len(args) < 1:
                return "Usage: !admin_bankrupt <@user or ticker>"
            return await admin_bankrupt(ctx, args[0], bot)
        
    except Exception as e:
        logger.error(f"Error processing command {command}: {e}", exc_info=True)
        return f"An error occurred: {str(e)}"
    
    return False

def setup(bot):
    """Setup commands"""
    logger.info("Setting up command processor")
    return True