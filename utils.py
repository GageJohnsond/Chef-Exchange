"""
Utility functions shared across the CH3F Exchange Discord Bot
"""
import asyncio
import logging
import discord

import config
from ui_components import ChartView
from stock_manager import StockManager

logger = logging.getLogger('ch3f_exchange.utilities')

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