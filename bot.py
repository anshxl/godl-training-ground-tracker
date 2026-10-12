"""
Main bot entry point for Discord Aim Training Tracker Bot.
Handles bot initialization, event handlers, and command routing.
"""

import os
import json
import logging
from pathlib import Path

import discord
from discord.ext import commands
from dotenv import load_dotenv

from database import Database
from handlers.scheduler import setup_scheduler
from handlers.training_api import start_training_api

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class AimTrackerBot(commands.Bot):
    """Custom bot class for the Aim Training Tracker."""

    def __init__(self, config: dict, database: Database):
        """
        Initialize the bot with configuration and database.

        Args:
            config: Configuration dictionary from config.json
            database: Database instance
        """
        # Set up intents
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True

        # Initialize bot with command prefix
        super().__init__(
            command_prefix=config['prefix'],
            intents=intents,
            help_command=None  # We'll create a custom help command
        )

        self.config = config
        self.db = database
        self.tracking_channel_id = int(os.getenv('TRACKING_CHANNEL_ID'))
        self.admin_role_id = int(os.getenv('ADMIN_ROLE_ID'))
        self.timezone = os.getenv('TIMEZONE', 'America/New_York')
        self.training_api_runner = None

    async def setup_hook(self):
        """Called when the bot is starting up. Load extensions here."""
        # Load message handler
        try:
            await self.load_extension('handlers.message_handler')
            logger.info("Message handler loaded successfully")
        except Exception as e:
            logger.error(f"Error loading message handler: {e}")

        # Load command modules
        try:
            await self.load_extension('commands.stats')
            await self.load_extension('commands.admin')
            logger.info("Command modules loaded successfully")
        except Exception as e:
            logger.error(f"Error loading command modules: {e}")

        # Setup scheduler for automated resets
        setup_scheduler(self)
        logger.info("Scheduler setup complete")

        # Read-only training API (only when TRAINING_API_TOKEN is set)
        await start_training_api(self)

    async def close(self):
        """Stop the training API (if running), then close the bot."""
        if self.training_api_runner:
            await self.training_api_runner.cleanup()
        await super().close()

    async def on_ready(self):
        """Called when the bot is ready and connected to Discord."""
        logger.info(f"Bot is ready! Logged in as {self.user.name} ({self.user.id})")
        logger.info(f"Tracking channel ID: {self.tracking_channel_id}")
        logger.info(f"Database: {self.config['database_path']}")
        logger.info(f"Timezone: {self.timezone}")

        # Set bot status
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name="for aim training screenshots"
            )
        )


def main():
    """Main entry point for the bot."""
    # Load configuration
    config_path = Path('config.json')
    if not config_path.exists():
        logger.error("config.json not found!")
        return

    with open(config_path, 'r') as f:
        config = json.load(f)

    # Check for required environment variables
    required_env_vars = ['DISCORD_TOKEN', 'TRACKING_CHANNEL_ID', 'ADMIN_ROLE_ID']
    missing_vars = [var for var in required_env_vars if not os.getenv(var)]
    if missing_vars:
        logger.error(f"Missing required environment variables: {', '.join(missing_vars)}")
        logger.error("Please create a .env file based on .env.example")
        return
    if not os.getenv('GEMINI_API_KEY'):
        logger.warning("GEMINI_API_KEY not set: screenshots are not validated, every image is accepted")

    # Initialize database
    db_path = config['database_path']
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)  # Create data directory
    database = Database(db_path)

    # Initialize and run bot
    bot = AimTrackerBot(config, database)

    # Get Discord token
    token = os.getenv('DISCORD_TOKEN')
    if not token:
        logger.error("DISCORD_TOKEN not found in environment variables!")
        return

    try:
        bot.run(token)
    except KeyboardInterrupt:
        logger.info("Bot shutdown requested by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
    finally:
        database.close()


if __name__ == '__main__':
    main()
