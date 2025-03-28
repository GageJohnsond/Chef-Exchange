"""
Admin Commands module for the Stock Exchange Discord Bot
"""
import random
import logging
from datetime import datetime, timezone
import asyncio

import discord

import config
from utils import create_stock_screener
from data_manager import DataManager
from user_manager import UserManager
from stock_manager import StockManager
from ui_components import ChartView, HelpView, BalanceLeaderboardView, StockLeaderboardView

logger = logging.getLogger('stock_exchange.admin_commands')

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

async def admin_set(ctx, target, amount, bot=None):
    """Admin command to set a stock's price to an exact value"""
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
    
    # Get current price for percentage calculation
    current_price = StockManager.stock_prices[symbol]
    
    # Calculate percentage change
    percentage_change = ((amount_value - current_price) / current_price) * 100
    
    # Update the price
    StockManager.stock_prices[symbol] = round(amount_value, 2)
    
    # Add to price history
    StockManager.price_history[symbol].append(round(amount_value, 2))
    
    # Save changes
    StockManager.save_stocks()
    
    # Create a response embed
    embed = discord.Embed(
        title="🔧 Admin: Stock Price Set",
        description=f"Set **{symbol}** price to **${amount_value:.2f}**",
        color=config.COLOR_WARNING
    )
    
    embed.add_field(
        name="Previous Price",
        value=f"${current_price:.2f}",
        inline=True
    )
    
    embed.add_field(
        name="New Price",
        value=f"${amount_value:.2f}",
        inline=True
    )
    
    embed.add_field(
        name="Change",
        value=f"{percentage_change:+.1f}%",
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

async def admin_gift(ctx, target, amount, bot=None):
    """Admin command to gift currency to a user"""
    # Security check - only allow specific admin users
    if ctx.author.id not in config.ADMIN_USER_IDS:
        return "❌ You don't have permission to use admin commands."

    # Parse amount
    try:
        amount_value = float(amount)
    except ValueError:
        return "⚠️ Invalid amount. Please enter a valid number."

    # Extract user ID from mention
    if not target.startswith('<@') or not target.endswith('>'):
        return "⚠️ Please mention a valid user with @username."
        
    user_id = target.strip('<@!>')
    
    if not user_id.isdigit():
        return "⚠️ Invalid user mention."
    
    # Ensure target user exists in database
    DataManager.ensure_user(user_id)
    
    # Get current balance
    current_balance = UserManager.get_balance(user_id)
    
    # Update user's balance
    UserManager.update_balance(user_id, amount_value)
    
    # Try to get user's name
    try:
        user = await bot.fetch_user(int(user_id))
        username = user.display_name
    except:
        username = f"User {user_id}"
    
    # Create a response embed
    embed = discord.Embed(
        title="💰 Admin Currency Action",
        description=f"{'Added' if amount_value >= 0 else 'Removed'} **${abs(amount_value):.2f} {config.UOM}** {'to' if amount_value >= 0 else 'from'} {target}",
        color=config.COLOR_WARNING
    )
    
    embed.add_field(
        name="Previous Balance",
        value=f"${current_balance:.2f}",
        inline=True
    )
    
    embed.add_field(
        name="New Balance",
        value=f"${(current_balance + amount_value):.2f}",
        inline=True
    )
    
    embed.add_field(
        name="Change",
        value=f"{'+' if amount_value >= 0 else '-'}${abs(amount_value):.2f}",
        inline=True
    )
    
    return embed

async def admin_create_stock(ctx, symbol, initial_price=None, user=None, bot=None):
    """Admin command to create a new stock with optional user assignment and initial price"""
    # Security check - only allow specific admin users
    if ctx.author.id not in config.ADMIN_USER_IDS:
        return "❌ You don't have permission to use admin commands."

    # Validate input
    if not symbol:
        return "⚠️ Please provide a valid stock symbol. Example: !admin_create_stock XYZ"
    
    # Format symbol properly
    symbol = symbol.upper()
    if not symbol.startswith('$'):
        symbol = f"${symbol}"
    
    # Validate symbol format - alphanumeric, 2-4 characters (not including $)
    import re
    if not re.match(r'^\$[A-Z0-9]{2,4}$', symbol):
        return "⚠️ Stock symbol must be 2-4 alphanumeric characters. Example: $XYZ"
    
    # Check if symbol already exists
    if symbol in StockManager.get_all_symbols():
        return f"⚠️ Stock symbol {symbol} already exists. Please choose another."
    
    # Parse initial price if provided
    price = None
    if initial_price:
        try:
            price = float(initial_price)
            if price <= 0:
                return "⚠️ Initial price must be positive."
        except ValueError:
            return "⚠️ Invalid initial price. Please enter a valid number."
    else:
        # Generate random price if not specified
        price = round(random.uniform(config.NEW_STOCK_MIN_PRICE, config.NEW_STOCK_MAX_PRICE), 2)
    
    # Process user assignment if provided
    user_id = None
    if user:
        if user.startswith('<@') and user.endswith('>'):
            user_id = user.strip('<@!>')
            if not user_id.isdigit():
                return "⚠️ Invalid user mention."
                
            # Check if user already has a stock
            existing_stock = StockManager.get_user_stock(user_id)
            if existing_stock:
                return f"⚠️ User already has a stock: {existing_stock}"
    
    # Add the stock
    StockManager.stock_symbols.append(symbol)
    StockManager.stock_prices[symbol] = round(price, 2)
    StockManager.price_history[symbol] = [round(price, 2)]
    
    # Associate with user if provided
    if user_id:
        StockManager.user_to_ticker[user_id] = symbol
    
    # Save changes
    StockManager.save_stocks()
    
    # Create stock screener message
    asyncio.create_task(create_stock_screener(ctx, symbol, bot))
    
    # Create response embed
    embed = discord.Embed(
        title="🔧 Admin: Stock Created",
        description=f"Created new stock **{symbol}** with initial price **${price:.2f} {config.UOM}**",
        color=config.COLOR_WARNING
    )
    
    if user_id:
        try:
            user_obj = await bot.fetch_user(int(user_id))
            embed.add_field(
                name="Associated User",
                value=f"{user}",
                inline=False
            )
        except:
            embed.add_field(
                name="Associated User ID",
                value=f"{user_id}",
                inline=False
            )
    
    return embed

async def admin_remove_stock(ctx, symbol, bot=None):
    """Admin command to remove a stock without bankruptcy"""
    # Security check - only allow specific admin users
    if ctx.author.id not in config.ADMIN_USER_IDS:
        return "❌ You don't have permission to use admin commands."

    # Validate input
    if not symbol:
        return "⚠️ Please provide a valid stock symbol."
    
    # Format symbol properly
    symbol = symbol.upper()
    if not symbol.startswith('$'):
        symbol = f"${symbol}"
    
    # Check if symbol exists
    if symbol not in StockManager.get_all_symbols():
        return f"⚠️ Stock symbol {symbol} not found."
    
    # Create confirmation message
    embed = discord.Embed(
        title="⚠️ STOCK REMOVAL CONFIRMATION",
        description=f"Are you sure you want to remove **{symbol}** from the exchange?\n\nThis will:\n- Remove the stock from the exchange\n- Delete all shares from user inventories\n- This action cannot be undone",
        color=config.COLOR_ERROR
    )
    
    # Create confirm/cancel buttons
    class RemoveConfirmView(discord.ui.View):
        def __init__(self, symbol, bot, original_user):
            super().__init__(timeout=60)
            self.symbol = symbol
            self.bot = bot
            self.original_user = original_user
        
        @discord.ui.button(label="Confirm Removal", style=discord.ButtonStyle.danger)
        async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
            # Check that only the original user can confirm
            if interaction.user.id != self.original_user.id:
                await interaction.response.send_message("Only the user who initiated this command can confirm it.", ephemeral=True)
                return
            
            try:
                # Process the removal similar to bankruptcy but without the 0 price
                announcement_data = await StockManager.handle_bankruptcy(self.symbol, bot)
                
                # Create response
                response_embed = discord.Embed(
                    title="🔧 STOCK REMOVED",
                    description=f"**{self.symbol}** has been removed from the exchange.",
                    color=config.COLOR_WARNING
                )
                
                # Add info about affected users
                if announcement_data:
                    affected_count = len(announcement_data)
                    response_embed.add_field(
                        name="Affected Users",
                        value=f"{affected_count} users had their shares of {self.symbol} removed.",
                        inline=False
                    )
                
                await interaction.response.edit_message(embed=response_embed, view=None)
            except Exception as e:
                error_embed = discord.Embed(
                    title="❌ Error",
                    description=f"An error occurred while removing the stock: {str(e)}",
                    color=config.COLOR_ERROR
                )
                await interaction.response.edit_message(embed=error_embed, view=None)
                logger.error(f"Error in admin_remove_stock: {e}", exc_info=True)
        
        @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
        async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
            await interaction.response.edit_message(
                embed=discord.Embed(
                    title="Action Cancelled",
                    description="Stock removal has been cancelled.",
                    color=config.COLOR_INFO
                ),
                view=None
            )
    
    # Send the confirmation message with buttons
    view = RemoveConfirmView(symbol, bot, ctx.author)
    message = await ctx.channel.send(embed=embed, view=view)
    
    # Return None because we've already sent our own message
    return None

async def admin_market_condition(ctx, condition=None, bot=None):
    """Admin command to view or change the market condition"""
    # Security check - only allow specific admin users
    if ctx.author.id not in config.ADMIN_USER_IDS:
        return "❌ You don't have permission to use admin commands."

    valid_conditions = ["bear", "bull", "volatile", "stable", "crash"]
    
    # If no condition specified, just report current status
    if not condition:
        embed = discord.Embed(
            title="🔧 Market Condition Status",
            description=f"Current market condition: **{StockManager.market_condition}**",
            color=config.COLOR_INFO
        )
        
        embed.add_field(
            name="Price Change Range",
            value=f"Min: {StockManager.current_min_change:.2f}\nMax: {StockManager.current_max_change:.2f}",
            inline=True
        )
        
        if StockManager.last_condition_change:
            embed.add_field(
                name="Last Changed",
                value=StockManager.last_condition_change,
                inline=True
            )
        
        return embed
    
    # Validate the requested condition
    condition = condition.lower()
    if condition not in valid_conditions:
        return f"⚠️ Invalid market condition. Valid options are: {', '.join(valid_conditions)}"
    
    # Define condition properties
    condition_properties = {
        "bear": {
            "min_change": random.uniform(-5, -1),
            "max_change": random.uniform(-1, 2),
        },
        "bull": {
            "min_change": random.uniform(-1, 1),
            "max_change": random.uniform(2, 5),
        },
        "volatile": {
            "min_change": random.uniform(-7, -3),
            "max_change": random.uniform(3, 7),
        },
        "stable": {
            "min_change": random.uniform(-3, -1),
            "max_change": random.uniform(1, 3),
        },
        "crash": {
            "min_change": random.uniform(-15, -8),
            "max_change": random.uniform(-8, -3),
        }
    }
    
    # Update market condition
    old_condition = StockManager.market_condition
    StockManager.market_condition = condition
    StockManager.current_min_change = condition_properties[condition]["min_change"]
    StockManager.current_max_change = condition_properties[condition]["max_change"]
    StockManager.last_condition_change = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    
    # Save changes
    StockManager.save_stocks()
    
    # Create response embed
    embed = discord.Embed(
        title="🔧 Market Condition Changed",
        description=f"Changed market condition from **{old_condition}** to **{condition}**",
        color=config.COLOR_WARNING
    )
    
    embed.add_field(
        name="New Price Change Range",
        value=f"Min: {StockManager.current_min_change:.2f}\nMax: {StockManager.current_max_change:.2f}",
        inline=False
    )
    
    # If condition is crash, send announcement to terminal channel
    if condition == "crash" and bot:
        try:
            terminal_channel = bot.get_channel(config.TERMINAL_CHANNEL_ID)
            if terminal_channel:
                # Create crash announcement embed
                crash_embed = discord.Embed(
                    title="🔥 MARKET CRASH DETECTED! 📉",
                    description="**EMERGENCY ALERT:** The market has entered a severe downturn!",
                    color=config.COLOR_ERROR
                )
                
                crash_embed.add_field(
                    name="What This Means",
                    value="All stocks are experiencing significant negative pressure. Stock prices are likely to fall sharply.",
                    inline=False
                )
                
                crash_embed.add_field(
                    name="Risk Level",
                    value="⚠️⚠️⚠️ HIGH - Multiple bankruptcies possible",
                    inline=False
                )
                
                crash_embed.add_field(
                    name="Investor Advice",
                    value="This may be a good time to buy stocks at discount prices if you're brave, or to hold onto cash if you're cautious.",
                    inline=False
                )
                
                crash_embed.set_footer(text=f"The {config.NAME} Exchange | Market Crash Triggered by Admin")
                
                await terminal_channel.send("@everyone", embed=crash_embed)
                logger.info(f"Admin {ctx.author.id} triggered market crash announcement")
                
                embed.add_field(
                    name="Announcement",
                    value="Crash announcement has been sent to the terminal channel.",
                    inline=False
                )
        except Exception as e:
            logger.error(f"Error sending crash announcement: {e}", exc_info=True)
            embed.add_field(
                name="Error",
                value=f"Failed to send crash announcement: {str(e)}",
                inline=False
            )
    
    return embed

async def admin_award_all(ctx, amount, bot=None):
    """Admin command to award currency to all users"""
    # Security check - only allow specific admin users
    if ctx.author.id not in config.ADMIN_USER_IDS:
        return "❌ You don't have permission to use admin commands."

    # Parse amount
    try:
        amount_value = float(amount)
    except ValueError:
        return "⚠️ Invalid amount. Please enter a valid number."

    # Load all user data
    data = DataManager.load_data(config.USER_DATA_FILE)
    
    # Keep track of how many users were updated
    updated_count = 0
    
    # Update each user's balance
    for user_id in data:
        data[user_id]["balance"] += amount_value
        updated_count += 1
    
    # Save changes
    DataManager.save_data(config.USER_DATA_FILE, data)
    
    # Create response embed
    embed = discord.Embed(
        title="🔧 Currency Awarded to All Users",
        description=f"{'Added' if amount_value >= 0 else 'Removed'} **${abs(amount_value):.2f} {config.UOM}** {'to' if amount_value >= 0 else 'from'} all users",
        color=config.COLOR_WARNING
    )
    
    embed.add_field(
        name="Affected Users",
        value=f"{updated_count} users",
        inline=False
    )
    
    return embed

async def admin_force_update(ctx, bot=None):
    """Admin command to force an immediate market update"""
    # Security check - only allow specific admin users
    if ctx.author.id not in config.ADMIN_USER_IDS:
        return "❌ You don't have permission to use admin commands."

    # Create pending message
    pending_embed = discord.Embed(
        title="🔧 Forcing Market Update",
        description="Updating all stock prices and charts...",
        color=config.COLOR_INFO
    )
    
    message = await ctx.channel.send(embed=pending_embed)
    
    try:
        # Import event handlers to access the update function
        from event_handlers import EventHandlers
        
        # Create a temporary EventHandlers instance
        handlers = EventHandlers(bot)
        
        # Force a market update
        bankruptcy_announcements = await StockManager.update_prices()
        
        # Update all stock charts
        await handlers.post_missing_stock_charts()
        
        # Update existing charts
        channel = bot.get_channel(config.STOCK_CHANNEL_ID)
        if channel:
            for symbol, message_id in StockManager.stock_messages.items():
                try:
                    chart_message = await channel.fetch_message(message_id)
                    view = ChartView(symbol)
                    view.message = chart_message
                    await view.update_chart()
                except Exception as e:
                    logger.error(f"Error updating chart for {symbol}: {e}")
        
        # Handle bankruptcy announcements if any
        if bankruptcy_announcements:
            terminal_channel = bot.get_channel(config.TERMINAL_CHANNEL_ID)
            if terminal_channel:
                for symbol, affected_users in bankruptcy_announcements.items():
                    embed = discord.Embed(
                        title=f"📉 Stock Bankruptcy: {symbol}",
                        description=f"**{symbol}** has gone bankrupt and has been delisted from the exchange!",
                        color=config.COLOR_ERROR
                    )
                    
                    # Add information about affected users
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
                    
                    await terminal_channel.send(embed=embed)
        
        # Update the leaderboards
        from leaderboard_manager import LeaderboardManager
        channel = bot.get_channel(config.LEADERBOARD_CHANNEL_ID)
        if channel and LeaderboardManager.balance_view and LeaderboardManager.balance_view.message:
            await LeaderboardManager.balance_view.update(channel.guild)
        
        if channel and LeaderboardManager.stock_view and LeaderboardManager.stock_view.message:
            await LeaderboardManager.stock_view.update()
        
        # Update response embed
        success_embed = discord.Embed(
            title="✅ Market Update Complete",
            description="Successfully updated all stock prices and charts.",
            color=config.COLOR_SUCCESS
        )
        
        # Add market condition info
        success_embed.add_field(
            name="Market Condition",
            value=f"**{StockManager.market_condition}**\nRange: {StockManager.current_min_change:.2f} to {StockManager.current_max_change:.2f}",
            inline=True
        )
        
        # Add stock info
        success_embed.add_field(
            name="Stocks Updated",
            value=f"{len(StockManager.stock_symbols)} active stocks",
            inline=True
        )
        
        # Add bankruptcy info if any
        if bankruptcy_announcements:
            success_embed.add_field(
                name="Bankruptcies",
                value=f"{len(bankruptcy_announcements)} stocks went bankrupt",
                inline=True
            )
        
        await message.edit(embed=success_embed)
        return None
        
    except Exception as e:
        # Update with error message
        error_embed = discord.Embed(
            title="❌ Market Update Failed",
            description=f"An error occurred: {str(e)}",
            color=config.COLOR_ERROR
        )
        
        await message.edit(embed=error_embed)
        logger.error(f"Error in admin_force_update: {e}", exc_info=True)
        return None
    
async def admin_help(ctx, bot=None):
    """Admin command to show a list of all admin commands"""
    # Security check - only allow specific admin users
    if ctx.author.id not in config.ADMIN_USER_IDS:
        return "❌ You don't have permission to use admin commands."
    
    # Create help embed with all admin commands
    embed = discord.Embed(
        title="🔧 Admin Commands",
        description=f"List of all available admin commands for the {config.NAME} Exchange Bot",
        color=config.COLOR_WARNING
    )
    
    # Stock price management commands
    embed.add_field(
        name="📈 Stock Price Management",
        value=(
            "`!admin_add <@user or ticker> <amount>` - Add value to a stock\n"
            "`!admin_sub <@user or ticker> <amount>` - Subtract value from a stock\n"
            "`!admin_set <@user or ticker> <amount>` - Set a stock price to an exact value\n"
            "`!admin_bankrupt <@user or ticker>` - Force a stock into bankruptcy"
        ),
        inline=False
    )
    
    # Stock creation/removal commands
    embed.add_field(
        name="🏭 Stock Management",
        value=(
            "`!admin_create_stock <symbol> [price] [@user]` - Create a new stock\n"
            "`!admin_remove_stock <symbol>` - Remove a stock without bankruptcy"
        ),
        inline=False
    )
    
    # User currency commands
    embed.add_field(
        name="💰 Currency Management",
        value=(
            "`!admin_gift <@user> <amount>` - Add/remove currency from a user\n"
            "`!admin_award_all <amount>` - Add/remove currency from all users"
        ),
        inline=False
    )
    
    # Market control commands
    embed.add_field(
        name="🌐 Market Control",
        value=(
            "`!admin_market [condition]` - View or change market condition\n"
            "`!admin_force_update` - Force an immediate market update"
        ),
        inline=False
    )
    
    # Help command
    embed.add_field(
        name="ℹ️ Help",
        value="`!admin_help` - Show this help message",
        inline=False
    )
    
    # Additional information
    embed.add_field(
        name="📝 Notes",
        value=(
            "• Market conditions: `bear`, `bull`, `volatile`, `stable`, `crash`\n"
            "• Use negative amounts with `admin_gift` to remove currency"
        ),
        inline=False
    )
    
    # Set footer with admin permission info
    embed.set_footer(text=f"Admin commands are restricted to users with admin privileges | Current admin IDs: {config.ADMIN_USER_IDS}")
    
    return embed
