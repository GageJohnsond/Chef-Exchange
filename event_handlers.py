"""
Event handlers module for Stock Exchange Discord Bot
Contains all event listener functions
"""
import asyncio
import logging
import random
import pytz
from datetime import datetime, timezone
from typing import Dict, List, Optional

import discord
from discord.ext import commands, tasks

import config
from dividends import DividendManager
from data_manager import DataManager
from user_manager import UserManager
from stock_manager import StockManager
from ui_components import ChartView

logger = logging.getLogger('stock_exchange.events')

class EventHandlers:
    """Class containing all event handler methods"""
    
    def __init__(self, bot):
        self.bot = bot
        self.stock_update_task = None
    
    async def on_ready(self):
        """Called when the bot is ready"""
        logger.info(f"Bot online as {self.bot.user}")
        
        # Initialize data and stock systems
        DataManager.ensure_files_exist()
        StockManager.load_stocks()
        StockManager.load_stock_messages()
        
        # Initialize leaderboard system
        from leaderboard_manager import LeaderboardManager
        LeaderboardManager.initialize(self.bot)
        asyncio.create_task(LeaderboardManager.setup_leaderboards())
        
        # Run emergency bankruptcy check on startup to catch any problematic stocks
        await StockManager.handle_emergency_bankruptcies(self.bot)
        
        # Start stock price update loop if not already running
        if self.stock_update_task is None or not self.stock_update_task.is_running():
            self.stock_update_task = self.update_stock_prices
            self.stock_update_task.start()

        #Start dividend payouts
        self.daily_dividend_distribution.start()

        # Post stock charts
        await self.post_all_stock_charts()
    
    async def on_message(self, message):
        """Called when a message is sent in any channel the bot can see"""
        if message.author.bot:
            return
        
        # Process commands if message starts with prefix
        if message.content.startswith('!'):
            try:
                # Import here to avoid circular imports
                from commands import process_command
                
                # Process the command
                result = await process_command(self.bot, message)
                
                # Send the response if there is one
                if result:
                    if isinstance(result, discord.Embed):
                        await message.channel.send(embed=result)
                    elif isinstance(result, str):
                        await message.channel.send(result)
                    # Some commands return None when they handle their own response
            except Exception as e:
                logger.error(f"Error processing command: {e}", exc_info=True)
                await message.channel.send(f"An error occurred processing your command: {str(e)}")
        
        # Award points for active channels
        if message.channel.id in config.ACTIVE_CHANNEL_IDS:
            user_id = str(message.author.id)
            utc_now = datetime.now(pytz.utc)
            eastern = pytz.timezone("America/New_York")
            est_now = utc_now.astimezone(eastern)
            today = est_now.strftime("%Y-%m-%d")
            data = DataManager.ensure_user(message.author.id)
            
            # Check for daily cap reset
            if data.get(user_id, {}).get("date") != today:
                data[user_id]["date"] = today
                data[user_id]["earned"] = 0
                logger.debug(f"Reset daily earnings for user {user_id}")
            
            # Award points if under daily cap
            if data[user_id]["earned"] < config.DAILY_CAP:
                points_to_add = min(
                    random.randint(config.MESSAGE_REWARD_MIN, config.MESSAGE_REWARD_MAX), 
                    config.DAILY_CAP - data[user_id]["earned"]
                )
                data[user_id]["balance"] += points_to_add
                data[user_id]["earned"] += points_to_add
                logger.debug(f"Awarded {points_to_add} to user {user_id} for message")
            
            DataManager.save_data(config.USER_DATA_FILE, data)
    
    async def on_reaction_add(self, reaction, user):
        """Called when a reaction is added to a message"""
        if user.bot or reaction.message.channel.id not in config.ACTIVE_CHANNEL_IDS:
            return
        
        data = DataManager.load_data(config.USER_DATA_FILE)
        message_author_id = str(reaction.message.author.id)
        reactor_id = str(user.id)
        
        # Ensure users exist
        if message_author_id not in data:
            data[message_author_id] = DataManager.ensure_user(message_author_id)[message_author_id]
        if reactor_id not in data:
            data[reactor_id] = DataManager.ensure_user(reactor_id)[reactor_id]
        
        # Award balance
        if message_author_id != reactor_id:  # Prevent self-rewarding
            reward = random.randint(
                config.REACTION_REWARD_AUTHOR_MIN, 
                config.REACTION_REWARD_AUTHOR_MAX
            )
            data[message_author_id]["balance"] += reward
            logger.debug(f"Awarded {reward} to message author {message_author_id} for reaction")
        
            reactor_reward = random.randint(
                config.REACTION_REWARD_REACTOR_MIN, 
                config.REACTION_REWARD_REACTOR_MAX
            )
            data[reactor_id]["balance"] += reactor_reward
            logger.debug(f"Awarded {reactor_reward} to reactor {reactor_id}")
        
        DataManager.save_data(config.USER_DATA_FILE, data)
    
    async def on_command_error(self, ctx, error):
        """Global error handler for commands"""
        if isinstance(error, commands.CommandNotFound):
            return  # Ignore invalid commands
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f"⚠️ Missing required argument: {error.param.name}")
        elif isinstance(error, commands.BadArgument):
            await ctx.send(f"⚠️ Invalid argument provided: {error}")
        else:
            logger.error(f"Command error: {error}")
            await ctx.send(f"❌ An error occurred: {error}")
    
    @tasks.loop(minutes=config.STOCK_UPDATE_INTERVAL)
    async def update_stock_prices(self):
        """Periodically update stock prices and edit existing messages"""
        logger.info("📊 Updating stock prices...")
        
        # Check the previous market condition
        previous_condition = StockManager.market_condition
        
        # Update stock prices
        bankruptcy_announcements = await StockManager.update_prices()
        
        # Check if the market condition has changed to crash
        if previous_condition != "crash" and StockManager.market_condition == "crash":
            # Send crash announcement
            await self.announce_market_crash()
        
        # Handle bankruptcy announcements if any
        if bankruptcy_announcements:
            await self.handle_bankruptcy_announcements(bankruptcy_announcements)
        
        # Edit stock messages
        channel = self.bot.get_channel(config.STOCK_CHANNEL_ID)
        if not channel:
            logger.warning("⚠️ Stock channel not found.")
            return
        
        # Create a copy of the dictionary to avoid modification during iteration
        messages_to_update = dict(StockManager.stock_messages)
        missing_messages = []
        
        for symbol, message_id in messages_to_update.items():
            try:
                message = await channel.fetch_message(message_id)
                view = ChartView(symbol)
                view.message = message
                await view.update_chart()
                logger.debug(f"Updated chart for {symbol}")
            except discord.NotFound:
                logger.warning(f"⚠️ Message for {symbol} not found. Will repost...")
                missing_messages.append(symbol)
        
        # Remove missing messages from original dictionary
        for symbol in missing_messages:
            if symbol in StockManager.stock_messages:
                del StockManager.stock_messages[symbol]
        
        # If any messages are missing, repost them
        if missing_messages:
            await self.post_missing_stock_charts()
        
        # Save the updated message IDs
        StockManager.save_stock_messages()
        logger.info("Stock update complete.")

    async def process_automatic_dividends(self):
        """Process dividends for all users regardless of daily claims"""
        logger.info("Processing automatic dividends for all users...")
        
        try:
            # Get a list of all users who haven't claimed dividends today
            utc_now = datetime.now(pytz.utc)
            eastern = pytz.timezone("America/New_York")
            est_now = utc_now.astimezone(eastern)
            today = est_now.strftime("%Y-%m-%d")
            
            user_data = DataManager.load_data(config.USER_DATA_FILE)
            users_to_process = []
            
            for user_id, data in user_data.items():
                last_dividend_date = data.get("last_dividend", {}).get("date", None)
                if last_dividend_date != today:
                    users_to_process.append(user_id)
            
            if not users_to_process:
                logger.info("No users need dividend processing")
                return
            
            # Process dividends for these users
            logger.info(f"Processing dividends for {len(users_to_process)} users")
            dividend_results = DividendManager.process_daily_dividends()
            
            # Get terminal channel for announcements
            channel = self.bot.get_channel(config.TERMINAL_CHANNEL_ID)
            if not channel:
                logger.warning("Terminal channel not found for dividend announcements")
                return
            
            # Create summary for announcement
            total_paid = 0
            for user_type in dividend_results.values():
                for amount in user_type.values():
                    total_paid += amount
            
            if total_paid > 0:
                # Create announcement embed
                embed = discord.Embed(
                    title="💰 Daily Dividend Distribution",
                    description=f"Stock dividends have been distributed to shareholders and stock owners!",
                    color=config.COLOR_SPECIAL
                )
                
                embed.add_field(
                    name="Total Dividends Paid",
                    value=f"**${total_paid:.2f} {config.UOM}**",
                    inline=False
                )
                
                embed.add_field(
                    name="Users Receiving Dividends",
                    value=f"{len(set(list(dividend_results['top_shareholders'].keys()) + list(dividend_results['creators'].keys())))}",
                    inline=True
                )
                
                embed.add_field(
                    name="Stocks Paying Owners from Investors",
                    value=f"{len(StockManager.get_all_symbols())}",
                    inline=True
                )
                
                embed.set_footer(text="Dividends are paid to top 3 shareholders and stock creators daily")
                
                await channel.send(embed=embed)
                logger.info(f"Dividend announcement sent, total paid: ${total_paid:.2f}")
        
        except Exception as e:
            logger.error(f"Error processing automatic dividends: {e}", exc_info=True)

    @tasks.loop(hours=24)
    async def daily_dividend_distribution(self):
        await self.process_automatic_dividends()
    
    async def handle_bankruptcy_announcements(self, bankruptcy_announcements):
        """Send announcements for stocks that went bankrupt"""
        if not bankruptcy_announcements:
            return
        
        # Get terminal channel for announcements
        channel = self.bot.get_channel(config.TERMINAL_CHANNEL_ID)
        if not channel:
            logger.warning("⚠️ Terminal channel not found for bankruptcy announcements.")
            return
        
        for symbol, affected_users in bankruptcy_announcements.items():
            # Create announcement embed
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
                        user = await self.bot.fetch_user(int(user_id))
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
            
            # Add footer
            embed.set_footer(text="All shares have been removed and the stock has been delisted.")
            
            # Send announcement
            try:
                await channel.send(embed=embed)
                logger.info(f"Sent bankruptcy announcement for {symbol}")
            except Exception as e:
                logger.error(f"Error sending bankruptcy announcement for {symbol}: {e}")
    
    async def announce_market_crash(self):
        """Send an announcement about a market crash"""
        channel = self.bot.get_channel(config.TERMINAL_CHANNEL_ID)
        if not channel:
            logger.warning("⚠️ Terminal channel not found for crash announcement.")
            return
        
        # Create crash announcement embed
        embed = discord.Embed(
            title="🔥 MARKET CRASH DETECTED! 📉",
            description="**EMERGENCY ALERT:** The market has entered a severe downturn!",
            color=config.COLOR_ERROR
        )
        
        embed.add_field(
            name="What This Means",
            value="All stocks are experiencing significant negative pressure. Stock prices are likely to fall sharply.",
            inline=False
        )
        
        embed.add_field(
            name="Risk Level",
            value="⚠️⚠️⚠️ HIGH - Multiple bankruptcies possible",
            inline=False
        )
        
        embed.add_field(
            name="Investor Advice",
            value="This may be a good time to buy stocks at discount prices if you're brave, or to hold onto cash if you're cautious.",
            inline=False
        )
        
        # Send the announcement
        try:
            await channel.send("@everyone", embed=embed)
            logger.info("Sent market crash announcement")
        except Exception as e:
            logger.error(f"Error sending market crash announcement: {e}")
        
    async def post_all_stock_charts(self):
        """Post all stock charts in the stock channel"""
        await self.bot.wait_until_ready()
        channel = self.bot.get_channel(config.STOCK_CHANNEL_ID)
        
        if not channel:
            logger.error("❌ Error: Stock channel not found. Check STOCK_CHANNEL_ID or bot permissions!")
            return
        
        logger.info("Posting stock charts...")
        
        # Use StockManager.get_all_symbols() instead of config.STOCK_SYMBOLS
        for symbol in StockManager.get_all_symbols():
            # Skip if message already exists and is valid
            if symbol in StockManager.stock_messages:
                try:
                    msg = await channel.fetch_message(StockManager.stock_messages[symbol])
                    logger.info(f"✅ Stock message for {symbol} already exists.")
                    continue
                except discord.NotFound:
                    logger.warning(f"⚠️ Stock message for {symbol} missing. Reposting...")
            
            # Create chart & embed
            view = ChartView(symbol)
            file, embed = await view.get_embed()
            
            # Send message
            try:
                message = await channel.send(embed=embed, file=file, view=view)
                StockManager.stock_messages[symbol] = message.id
                view.message = message
                logger.info(f"📊 Sent stock chart for {symbol}.")
                
                # Add a small delay to avoid rate limits
                await asyncio.sleep(1)
            except Exception as e:
                logger.error(f"Error posting chart for {symbol}: {e}")
        
        # Save message IDs
        StockManager.save_stock_messages()
    
    async def post_missing_stock_charts(self):
        """Post only missing stock charts"""
        await self.bot.wait_until_ready()
        channel = self.bot.get_channel(config.STOCK_CHANNEL_ID)
        
        if not channel:
            logger.error("❌ Error: Stock channel not found!")
            return
        
        logger.info("Posting missing stock charts...")
        
        # Use StockManager.get_all_symbols() instead of config.STOCK_SYMBOLS
        for symbol in StockManager.get_all_symbols():
            # Skip if message already exists
            if symbol in StockManager.stock_messages:
                continue
            
            # Create chart & embed
            view = ChartView(symbol)
            file, embed = await view.get_embed()
            
            # Send message
            try:
                message = await channel.send(embed=embed, file=file, view=view)
                StockManager.stock_messages[symbol] = message.id
                view.message = message
                logger.info(f"📊 Sent stock chart for {symbol}.")
                
                # Add a small delay to avoid rate limits
                await asyncio.sleep(1)
            except Exception as e:
                logger.error(f"Error posting chart for {symbol}: {e}")
        
        # Save message IDs
        StockManager.save_stock_messages()

def setup(bot):
    """Initialize event handlers and register them with the bot"""
    events = EventHandlers(bot)
    
    # Register event handlers
    bot.event(events.on_ready)
    bot.event(events.on_message)
    bot.event(events.on_reaction_add)
    bot.event(events.on_command_error)
    
    return events