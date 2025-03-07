"""
Event handlers module for CH3F Exchange Discord Bot
Contains all event listener functions
"""
import asyncio
import logging
import random
from datetime import datetime, timezone
from typing import Dict, List, Optional

import discord
from discord.ext import commands, tasks

import config
from data_manager import DataManager
from user_manager import UserManager
from stock_manager import StockManager
from ui_components import ChartView

logger = logging.getLogger('ch3f_exchange.events')

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
        
        # Start stock price update loop if not already running
        if self.stock_update_task is None or not self.stock_update_task.is_running():
            self.stock_update_task = self.update_stock_prices
            self.stock_update_task.start()
        
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
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
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
        
        # Update stock prices
        StockManager.update_prices()
        
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
    
    async def post_all_stock_charts(self):
        """Post all stock charts in the stock channel"""
        await self.bot.wait_until_ready()
        channel = self.bot.get_channel(config.STOCK_CHANNEL_ID)
        
        if not channel:
            logger.error("❌ Error: Stock channel not found. Check STOCK_CHANNEL_ID or bot permissions!")
            return
        
        logger.info("Posting stock charts...")
        
        for symbol in config.STOCK_SYMBOLS:
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
        
        for symbol in config.STOCK_SYMBOLS:
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