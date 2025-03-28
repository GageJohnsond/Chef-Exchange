"""
Commands module for Stock Exchange Discord Bot
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

logger = logging.getLogger('stock_exchange.commands')

# Export the process_command function at the module level
__all__ = ['process_command', 'setup']

def balance(ctx):
    """Check your balance command"""
    DataManager.ensure_user(ctx.author.id)
    bal = UserManager.get_balance(ctx.author.id)
    bank_amt = UserManager.get_bank(ctx.author.id)
    
    embed = discord.Embed(
        title="💰 Balance",
        description=f"Your balance: **${bal:.2f} {config.UOM}**",
        color=config.COLOR_INFO
    )
    
    if bank_amt > 0:
        embed.add_field(name="Bank Balance", value=f"**${bank_amt:.2f} {config.UOM}**")
    
    return embed

def daily(ctx):
    """Claim daily reward command with dividend payments"""
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
    
    # Process dividends
    from dividends import DividendManager
    dividend_results = DividendManager.process_daily_dividends()
    
    # Check if user received dividends
    shareholder_dividend = dividend_results["top_shareholders"].get(user_id, 0)
    creator_dividend = dividend_results["creators"].get(user_id, 0)
    total_dividend = shareholder_dividend + creator_dividend
    
    DataManager.save_data(config.USER_DATA_FILE, data)
    
    # Create response embed
    embed = discord.Embed(
        title="🎁 Daily Reward",
        description=f"You claimed your daily **${reward:.2f} {config.UOM}**!",
        color=config.COLOR_WARNING
    )
    
    # Add dividend info if applicable
    if total_dividend > 0:
        embed.add_field(
            name="💰 Stock Dividends",
            value=f"You also received **${total_dividend:.2f} {config.UOM}** in dividends!",
            inline=False
        )
        
        if shareholder_dividend > 0:
            embed.add_field(
                name="Shareholder Dividends",
                value=f"**${shareholder_dividend:.2f} {config.UOM}**",
                inline=True
            )
        
        if creator_dividend > 0:
            embed.add_field(
                name="Money from Investors",
                value=f"**${creator_dividend:.2f} {config.UOM}**",
                inline=True
            )
    
    return embed

def gift(ctx, user, amount):
    """Gift $ to another user"""
    # Validate input
    if amount <= 0:
        return "⚠️ Invalid amount. Please enter a positive number."
    
    # Ensure both users exist in database
    DataManager.ensure_user(ctx.author.id)
    DataManager.ensure_user(user.id)
    
    # Check balance
    bal = UserManager.get_balance(ctx.author.id)
    if bal < amount:
        return f"❌ You don't have enough ${config.UOM} for this gift."
    
    # Transfer the amount
    UserManager.update_balance(ctx.author.id, -amount)
    UserManager.update_balance(user.id, amount)
    
    # Send confirmation
    embed = discord.Embed(
        title="🎁 Gift Sent",
        description=f"You gifted **${amount:.2f} {config.UOM}** to {user.mention}!",
        color=config.COLOR_SPECIAL
    )
    
    return embed

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
            desc += f"{stock}: **x{quantity}** (${value:.2f} {config.UOM})\n"
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
        value=f"**${total_value:.2f} {config.UOM}**"
    )
    
    return embed

async def rebrand_stock(ctx, new_symbol, bot=None):
    """Allow a user to change their stock symbol for a fee"""
    # Validate input
    if not new_symbol:
        return "⚠️ Please specify a new stock symbol. Example: !rebrand XYZ"
    
    # Format symbol properly
    new_symbol = new_symbol.upper()
    if not new_symbol.startswith('$'):
        new_symbol = f"${new_symbol}"
    
    # Validate symbol format - alphanumeric, 2-4 characters (not including $)
    import re
    if not re.match(r'^\$[A-Z0-9]{2,4}$', new_symbol):
        return "⚠️ Stock symbol must be 2-4 alphanumeric characters. Example: $XYZ"
    
    # Check if user has a stock
    user_id = str(ctx.author.id)
    current_symbol = StockManager.get_user_stock(user_id)
    
    if not current_symbol:
        return f"⚠️ You don't own a stock to rebrand. Create one first with !createstock"
    
    # Check if new symbol already exists
    if new_symbol in StockManager.get_all_symbols():
        return f"⚠️ Stock symbol {new_symbol} already exists. Please choose another."
        
    # Check if user has enough funds
    DataManager.ensure_user(ctx.author.id)
    bal = UserManager.get_balance(ctx.author.id)
        
    if bal < config.REBRAND_FEE:
        return f"❌ Insufficient funds. Rebranding costs ${config.REBRAND_FEE} {config.UOM}. You have ${bal:.2f} {config.UOM}."
    
    # Create confirmation message
    embed = discord.Embed(
        title="🔄 Stock Rebranding Confirmation",
        description=f"Are you sure you want to rebrand your stock from **{current_symbol}** to **{new_symbol}**?\n\nThis will cost **${config.REBRAND_FEE} {config.UOM}**.",
        color=config.COLOR_WARNING
    )
    
    # Create confirm/cancel buttons
    class RebrandConfirmView(discord.ui.View):
        def __init__(self, current_symbol, new_symbol, user_id, bot, original_user):
            super().__init__(timeout=60)
            self.current_symbol = current_symbol
            self.new_symbol = new_symbol
            self.user_id = user_id
            self.bot = bot
            self.original_user = original_user
        
        @discord.ui.button(label="Confirm Rebrand", style=discord.ButtonStyle.primary)
        async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
            # Check that only the original user can confirm
            if interaction.user.id != self.original_user.id:
                await interaction.response.send_message("Only the user who initiated this command can confirm it.", ephemeral=True)
                return
            
            # Charge the user
            UserManager.update_balance(self.user_id, -config.REBRAND_FEE)
            
            try:
                # Delete the old stock message if it exists
                if self.current_symbol in StockManager.stock_messages:
                    message_id = StockManager.stock_messages[self.current_symbol]
                    
                    try:
                        channel = self.bot.get_channel(config.STOCK_CHANNEL_ID)
                        if channel:
                            message = await channel.fetch_message(message_id)
                            await message.delete()
                            logger.info(f"Deleted old stock message for {self.current_symbol}")
                    except discord.NotFound:
                        logger.warning(f"Old stock message for {self.current_symbol} not found")
                    except Exception as e:
                        logger.error(f"Error deleting old stock message: {e}")
                    
                    # Remove old message ID
                    del StockManager.stock_messages[self.current_symbol]
                
                # Change symbol in stock_symbols list
                index = StockManager.stock_symbols.index(self.current_symbol)
                StockManager.stock_symbols[index] = self.new_symbol
                
                # Update price and history tracking
                price = StockManager.stock_prices[self.current_symbol]
                history = StockManager.price_history[self.current_symbol]
                
                # Add new entries
                StockManager.stock_prices[self.new_symbol] = price
                StockManager.price_history[self.new_symbol] = history
                
                # Remove old entries
                del StockManager.stock_prices[self.current_symbol]
                del StockManager.price_history[self.current_symbol]
                
                # Update user to ticker mapping
                StockManager.user_to_ticker[self.user_id] = self.new_symbol
                
                # Update all user inventories that hold this stock
                user_data = DataManager.load_data(config.USER_DATA_FILE)
                updated_users = 0
                
                for uid, data in user_data.items():
                    if "inventory" in data and self.current_symbol in data["inventory"]:
                        # Transfer shares to new symbol
                        shares = data["inventory"][self.current_symbol]
                        data["inventory"][self.new_symbol] = shares
                        del data["inventory"][self.current_symbol]
                        updated_users += 1
                
                # Save user data
                DataManager.save_data(config.USER_DATA_FILE, user_data)
                
                # Save stock changes
                StockManager.save_stocks()
                StockManager.save_stock_messages()
                
                # Create new stock screener
                from utils import create_stock_screener
                await create_stock_screener(interaction, self.new_symbol, self.bot)
                
                # Create response
                response_embed = discord.Embed(
                    title="✅ Stock Rebranding Complete",
                    description=f"Successfully rebranded your stock from **{self.current_symbol}** to **{self.new_symbol}**.",
                    color=config.COLOR_SUCCESS
                )
                
                response_embed.add_field(
                    name="Current Price",
                    value=f"${price:.2f} {config.UOM}",
                    inline=True
                )
                
                response_embed.add_field(
                    name="Updated Inventories",
                    value=f"{updated_users} users' holdings updated",
                    inline=True
                )
                
                response_embed.add_field(
                    name="Fee Paid",
                    value=f"${config.REBRAND_FEE} {config.UOM}",
                    inline=True
                )
                
                await interaction.response.edit_message(embed=response_embed, view=None)
                
                # Announce the rebrand in terminal channel
                try:
                    terminal_channel = self.bot.get_channel(config.TERMINAL_CHANNEL_ID)
                    if terminal_channel:
                        announce_embed = discord.Embed(
                            title="🔄 Stock Rebranding Announcement",
                            description=f"<@{self.user_id}> has rebranded their stock from **{self.current_symbol}** to **{self.new_symbol}**.",
                            color=config.COLOR_INFO
                        )
                        await terminal_channel.send(embed=announce_embed)
                except Exception as e:
                    logger.error(f"Error sending rebrand announcement: {e}")
                
            except Exception as e:
                # If something goes wrong, refund the user
                UserManager.update_balance(self.user_id, config.REBRAND_FEE)
                
                error_embed = discord.Embed(
                    title="❌ Rebranding Failed",
                    description=f"An error occurred during rebranding: {str(e)}\n\nYour fee has been refunded.",
                    color=config.COLOR_ERROR
                )
                await interaction.response.edit_message(embed=error_embed, view=None)
                logger.error(f"Error during stock rebranding: {e}", exc_info=True)
        
        @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
        async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
            await interaction.response.edit_message(
                embed=discord.Embed(
                    title="Action Cancelled",
                    description="Stock rebranding has been cancelled. No fee was charged.",
                    color=config.COLOR_INFO
                ),
                view=None
            )
    
    # Send the confirmation message with buttons
    view = RebrandConfirmView(current_symbol, new_symbol, user_id, bot, ctx.author)
    message = await ctx.channel.send(embed=embed, view=view)
    
    # Return None because we've already sent our own message
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
        return f"❌ Insufficient funds. Creating a stock costs ${config.IPO_COST} {config.UOM}. You have ${bal:.2f} {config.UOM}."
        
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
        description=f"Congratulations {ctx.author.mention}! You've successfully created **{symbol}** stock.\nStarting price: **${StockManager.stock_prices[symbol]:.2f} {config.UOM}**",
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
        title=f"About The {config.NAME} Exchange",
        description=f"This is a bot built to simulate the {config.NAME} Exchange.",
        color=config.COLOR_DISCORD
    )
    
    embed.add_field(
        name="Creator",
        value="Created by Gage Johnson."
    )
    
    embed.add_field(
        name="Features",
        value=f"• Virtual currency (${config.UOM})\n• Stock market simulation\n• Interactive commands\n• Reaction rewards"
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

def dividend_status(ctx):
    """Check your dividend earnings"""
    user_id = str(ctx.author.id)
    DataManager.ensure_user(user_id)
    
    # Load user data
    data = DataManager.load_data(config.USER_DATA_FILE)
    
    # Get stocks created by user
    owned_stock_symbol = None
    for uid, ticker in StockManager.user_to_ticker.items():
        if uid == user_id:
            owned_stock_symbol = ticker
            break
    
    # Get stocks where user is top shareholder
    top_shareholder_stocks = []
    for symbol in StockManager.get_all_symbols():
        # Find all shareholders
        shareholders = []
        for uid, udata in data.items():
            inventory = udata.get("inventory", {})
            if symbol in inventory and inventory[symbol] > 0:
                shareholders.append((uid, inventory[symbol]))
        
        # Sort by shares
        shareholders.sort(key=lambda x: x[1], reverse=True)
        
        # Check if user is in top 3
        for rank, (shareholder_id, shares) in enumerate(shareholders[:config.TOP_SHAREHOLDERS_COUNT]):
            if shareholder_id == user_id:
                top_shareholder_stocks.append((symbol, shares, rank + 1))
                break
    
    # Get last dividend payment
    last_dividend = data[user_id].get("last_dividend", {})
    last_date = last_dividend.get("date", "Never")
    last_amount = last_dividend.get("amount", 0)
    
    # Create embed
    embed = discord.Embed(
        title="💰 Dividend Status",
        description=f"Your dividend earning status",
        color=config.COLOR_INFO
    )
    
    # Last payment
    embed.add_field(
        name="Last Dividend Payment",
        value=f"**${last_amount:.2f} {config.UOM}** on {last_date}" if last_amount > 0 else "No recent dividends",
        inline=False
    )
    
    # Creator status
    if owned_stock_symbol:
        stock_price = StockManager.stock_prices.get(owned_stock_symbol, 0)
        
        # Count shares owned by others
        other_shares = 0
        for uid, udata in data.items():
            if uid != user_id:
                inventory = udata.get("inventory", {})
                if owned_stock_symbol in inventory:
                    other_shares += inventory[owned_stock_symbol]
        
        estimated_dividend = round(stock_price * (config.CREATOR_DIVIDEND_PERCENT / 100) * other_shares, 2)
        
        embed.add_field(
            name=f"Owned Stock: {owned_stock_symbol}",
            value=(
                f"Current price: **${stock_price:.2f} {config.UOM}**\n"
                f"Shares held by others: **{other_shares}**\n"
                f"Est. daily stock income from investors: **${estimated_dividend:.2f} {config.UOM}**"
            ),
            inline=False
        )
    else:
        embed.add_field(
            name="Stock Creator Status",
            value="You don't own a stock. Create one with `!createstock <symbol>`",
            inline=False
        )
    
    # Top shareholder status
    if top_shareholder_stocks:
        shareholder_desc = ""
        for symbol, shares, rank in top_shareholder_stocks:
            stock_price = StockManager.stock_prices.get(symbol, 0)
            percent = config.TOP_SHAREHOLDER_DIVIDENDS.get(rank - 1, 0)
            estimated_dividend = round(stock_price * (percent / 100), 2)
            
            shareholder_desc += (
                f"**{symbol}** - Rank #{rank} with {shares} shares\n"
                f"Est. daily dividend: **${estimated_dividend:.2f} {config.UOM}**\n\n"
            )
        
        embed.add_field(
            name="Top Shareholder Positions",
            value=shareholder_desc,
            inline=False
        )
    else:
        embed.add_field(
            name="Top Shareholder Status",
            value="You're not a top 3 shareholder in any stocks\nBuy more shares to earn dividends!",
            inline=False
        )
    
    embed.set_footer(text=f"Dividends are paid to the top {config.TOP_SHAREHOLDERS_COUNT} shareholders of each stock. Stock owners will earn income from investors.")

    return embed

def decay_risk(ctx):
    """Check which stocks are at risk of decay"""
    # Import decay manager
    from decay import DecayManager
    
    # Get total stocks
    total_stocks = len(StockManager.get_all_symbols())
    threshold = config.STOCK_DECAY_THRESHOLD
    
    # Create embed based on current situation
    if total_stocks <= threshold:
        # No decay risk currently
        embed = discord.Embed(
            title="📊 Stock Decay Status",
            description=f"There are currently **{total_stocks}/{threshold}** stocks on the exchange.",
            color=config.COLOR_SUCCESS
        )
        
        embed.add_field(
            name="Status",
            value=f"No stocks are at risk of decay at this time.",
            inline=False
        )
        
        # Add information about how decay works
        embed.add_field(
            name="About Stock Decay",
            value=(
                f"When the number of stocks exceeds {threshold}, the least popular "
                f"stocks will lose their value overtime."
            ),
            inline=False
        )
    else:
        # Calculate stocks at risk
        excess = total_stocks - threshold
        risk_stocks = DecayManager.get_decay_risk_stocks()
        
        embed = discord.Embed(
            title="⚠️ Stock Decay Warning",
            description=(
                f"There are currently **{total_stocks}/{threshold}** stocks on the exchange.\n"
                f"**{excess}** stocks are experiencing price decay!"
            ),
            color=config.COLOR_ERROR
        )
        
        # Add list of stocks at risk
        if risk_stocks:
            # Group by risk level
            definite_decay = []
            high_risk = []
            medium_risk = []
            low_risk = []
            
            for symbol, risk in risk_stocks:
                if risk >= 90:
                    definite_decay.append(symbol)
                elif risk >= 50:
                    high_risk.append(symbol)
                elif risk >= 25:
                    medium_risk.append(symbol)
                else:
                    low_risk.append(symbol)
            
            # Add fields for each risk level
            if definite_decay:
                embed.add_field(
                    name="🔴 Currently Decaying",
                    value=", ".join([f"**{s}**" for s in definite_decay]),
                    inline=False
                )
            
            if high_risk:
                embed.add_field(
                    name="🟠 High Risk (50-90%)",
                    value=", ".join([f"**{s}**" for s in high_risk]),
                    inline=False
                )
            
            if medium_risk:
                embed.add_field(
                    name="🟡 Medium Risk (25-50%)",
                    value=", ".join([f"**{s}**" for s in medium_risk]),
                    inline=False
                )
            
            if low_risk:
                embed.add_field(
                    name="🟢 Low Risk (<25%)",
                    value=", ".join([f"**{s}**" for s in low_risk]),
                    inline=False
                )
        
        # Add explanation of what decay means
        embed.add_field(
            name="How Decay Works",
            value=(f"Decaying stocks lose value overtime. To prevent decay, these stocks need more shareholders!\n"),
            inline=False
        )
        
        # Add advice for owners of at-risk stocks
        embed.add_field(
            name="If Your Stock Is At Risk",
            value=(
                "• Encourage others to invest in your stock\n"
                "• Consider offering incentives to shareholders\n"
                "• If price gets too low, you risk bankruptcy"
            ),
            inline=False
        )
    
    return embed

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
                        return f"Please mention a user to gift {config.UOM} to."
                    user = bot.get_user(int(user_id)) or await bot.fetch_user(int(user_id))
                
                amount = float(args[1])
                return gift(ctx, user, amount)
            except (ValueError, IndexError) as e:
                logger.error(f"Error in gift command: {e}")
                return "Invalid amount. Please use the format: !gift @user amount"
        
        elif command in ['dividends', 'div']:
            return dividend_status(ctx)

        elif command in ['decayrisk', 'stockrisk']:
            return decay_risk(ctx)
        
        elif command in ['mystocks', 'portfolio', 'port']:
            return mystocks(ctx)
        
        elif command in ['rebrand', 'rename']:
            if len(args) < 1:
                return "Please specify a new stock symbol. Example: !rebrand XYZ"
            return await rebrand_stock(ctx, args[0], bot)
        
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