"""
Main entry point for CH3F Exchange Discord Bot
"""
import logging
import sys

import discord
from discord.ext import commands

import config
from commands import setup as setup_commands
from event_handlers import setup as setup_events

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('bot.log', encoding='utf-8')
    ]
)
logger = logging.getLogger('ch3f_exchange')

def create_bot():
    """Create and configure the bot instance"""
    # Setup intents
    intents = discord.Intents.default()
    intents.messages = True
    intents.message_content = True
    intents.guilds = True
    intents.members = True
    intents.reactions = True
    
    # Create bot instance with no command prefix
    bot = commands.Bot(command_prefix=None, intents=intents)
    
    # Disable the default command processing
    bot._skip_check = lambda *args, **kwargs: True
    
    return bot

def main():
    """Main function to start the bot"""
    logger.info("Starting CH3F Exchange bot...")
    
    # Create bot instance
    bot = create_bot()
    
    try:
        # Setup commands and event handlers
        setup_commands(bot)
        event_handlers = setup_events(bot)
        
        # Run the bot
        if not config.TOKEN:
            logger.error("No Discord bot token found! Please set the DISCORD_BOT_TOKEN environment variable.")
            return
        
        logger.info("Connecting to Discord...")
        bot.run(config.TOKEN)
    except discord.LoginFailure:
        logger.error("Invalid bot token. Please check your .env file or environment variables.")
    except KeyboardInterrupt:
        logger.info("Bot shutdown initiated by user.")
    except Exception as e:
        logger.error(f"Error starting bot: {e}", exc_info=True)

if __name__ == "__main__":
    main()