"""
Leaderboard management module for Stock Exchange Discord Bot
Handles the persistent leaderboard messages
"""
import json
import logging
import asyncio
from typing import Dict, Optional

import discord
from discord.ext import tasks

import config
from ui_components import BalanceLeaderboardView, StockLeaderboardView

logger = logging.getLogger('stock_exchange.leaderboard')

class LeaderboardManager:
    """Class to handle persistent leaderboard messages"""
    
    # Class variables to store message IDs and views
    balance_leaderboard_id = None
    stock_leaderboard_id = None
    
    balance_view = None
    stock_view = None
    
    # Store reference to the bot
    bot = None
    
    # Path to store message IDs
    LEADERBOARD_FILE = "leaderboard_messages.json"
    
    @classmethod
    def initialize(cls, bot):
        """Initialize the leaderboard manager"""
        cls.bot = bot
        cls._load_message_ids()
        
        # Create views
        cls.balance_view = BalanceLeaderboardView()
        cls.stock_view = StockLeaderboardView()
        
        logger.info("Leaderboard manager initialized")
    
    @classmethod
    def _load_message_ids(cls):
        """Load message IDs from file"""
        try:
            with open(cls.LEADERBOARD_FILE, "r") as f:
                data = json.load(f)
                cls.balance_leaderboard_id = data.get("balance")
                cls.stock_leaderboard_id = data.get("stocks")
                logger.info("Loaded leaderboard message IDs")
        except (FileNotFoundError, json.JSONDecodeError):
            # Create empty file if it doesn't exist
            cls._save_message_ids()
    
    @classmethod
    def _save_message_ids(cls):
        """Save message IDs to file"""
        data = {
            "balance": cls.balance_leaderboard_id,
            "stocks": cls.stock_leaderboard_id
        }
        
        try:
            with open(cls.LEADERBOARD_FILE, "w") as f:
                json.dump(data, f, indent=0)
            logger.info("Saved leaderboard message IDs")
        except Exception as e:
            logger.error(f"Error saving leaderboard message IDs: {e}")
    
    @classmethod
    async def setup_leaderboards(cls):
        """Set up the persistent leaderboard messages"""
        await cls.bot.wait_until_ready()
        
        # Get the leaderboard channel
        channel = cls.bot.get_channel(config.LEADERBOARD_CHANNEL_ID)
        
        if not channel:
            logger.error(f"Leaderboard channel (ID: {config.LEADERBOARD_CHANNEL_ID}) not found")
            return
        
        # Check for existing balance leaderboard message
        if cls.balance_leaderboard_id:
            try:
                message = await channel.fetch_message(cls.balance_leaderboard_id)
                cls.balance_view.message = message
                logger.info("Found existing balance leaderboard message")
            except discord.NotFound:
                cls.balance_leaderboard_id = None
                logger.warning("Balance leaderboard message not found, will create a new one")
        
        # Check for existing stock leaderboard message
        if cls.stock_leaderboard_id:
            try:
                message = await channel.fetch_message(cls.stock_leaderboard_id)
                cls.stock_view.message = message
                logger.info("Found existing stock leaderboard message")
            except discord.NotFound:
                cls.stock_leaderboard_id = None
                logger.warning("Stock leaderboard message not found, will create a new one")
        
        # Create new leaderboard messages if needed
        await cls._create_missing_leaderboards(channel)
        
        # Start update tasks
        if not cls.update_leaderboards.is_running():
            cls.update_leaderboards.start()
            logger.info("Started leaderboard update task")
    
    @classmethod
    async def _create_missing_leaderboards(cls, channel):
        """Create missing leaderboard messages"""
        # Create balance leaderboard if missing
        if not cls.balance_leaderboard_id:
            embed = cls.balance_view.get_embed(channel.guild)
            
            message = await channel.send(
                f"🏆 **${config.UOM} BALANCE LEADERBOARD**\nThis message updates automatically.",
                embed=embed,
                view=cls.balance_view
            )
            
            cls.balance_leaderboard_id = message.id
            cls.balance_view.message = message
            logger.info("Created new balance leaderboard message")
        
        # Create stock leaderboard if missing
        if not cls.stock_leaderboard_id:
            embed = cls.stock_view.get_embed()
            
            message = await channel.send(
                "📊 **STOCK PRICE LEADERBOARD**\nThis message updates automatically.",
                embed=embed,
                view=cls.stock_view
            )
            
            cls.stock_leaderboard_id = message.id
            cls.stock_view.message = message
            logger.info("Created new stock leaderboard message")
        
        # Save message IDs
        cls._save_message_ids()
    
    @classmethod
    @tasks.loop(minutes=config.LEADERBOARD_UPDATE_INTERVAL)
    async def update_leaderboards(cls):
        """Periodically update the leaderboard messages"""
        logger.info("Updating leaderboard messages...")
        
        channel = cls.bot.get_channel(config.LEADERBOARD_CHANNEL_ID)
        if not channel:
            logger.error("Leaderboard channel not found")
            return
        
        # Update balance leaderboard
        if cls.balance_view and cls.balance_view.message:
            try:
                await cls.balance_view.update(channel.guild)
                logger.info("Updated balance leaderboard")
            except Exception as e:
                logger.error(f"Error updating balance leaderboard: {e}")
        
        # Update stock leaderboard
        if cls.stock_view and cls.stock_view.message:
            try:
                await cls.stock_view.update()
                logger.info("Updated stock leaderboard")
            except Exception as e:
                logger.error(f"Error updating stock leaderboard: {e}")