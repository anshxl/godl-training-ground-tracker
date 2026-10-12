"""
Message handler for tracking screenshot submissions.
Monitors designated channel for image attachments and logs submissions.
"""

import logging
import discord
from discord.ext import commands
from utils.image_validator import validate_aim_screenshot

logger = logging.getLogger(__name__)


class MessageHandler(commands.Cog):
    """Handles screenshot submission tracking."""

    def __init__(self, bot):
        """
        Initialize the message handler.

        Args:
            bot: The bot instance
        """
        self.bot = bot
        self.db = bot.db
        self.tracking_channel_id = bot.tracking_channel_id

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """
        Handle incoming messages and check for screenshot submissions.

        Args:
            message: The Discord message object
        """
        # Ignore bot messages
        if message.author.bot:
            return

        # Check if message is in the tracking channel
        if message.channel.id != self.tracking_channel_id:
            return

        # The first image attachment is the submission
        image = self._first_image(message)
        if image is None:
            return

        await self._process_submission(message, image)

    def _first_image(self, message: discord.Message):
        """Return the first image attachment of a message, or None."""
        image_extensions = ('.png', '.jpg', '.jpeg', '.gif', '.webp')
        for attachment in message.attachments:
            if attachment.filename.lower().endswith(image_extensions):
                return attachment
        return None

    async def _process_submission(self, message: discord.Message, image: discord.Attachment):
        """
        Process a screenshot submission.

        Args:
            message: The Discord message object
            image: The image attachment to validate and log
        """
        discord_id = str(message.author.id)
        username = message.author.name
        image_url = image.url
        filename = image.filename

        try:
            # Add or update player in database
            self.db.add_or_update_player(discord_id, username)

            # Check if this filename has already been submitted by this player
            if self.db.has_duplicate_filename(discord_id, filename):
                await self._send_duplicate_file_message(message, filename)
                logger.info(f"Duplicate filename detected: {username} ({discord_id}) - {filename}")
                return

            # Validate image using Gemini VLM
            logger.info(f"Validating screenshot from {username} ({discord_id})")
            is_valid, validation_reason = await validate_aim_screenshot(
                await image.read(), image.content_type or 'image/jpeg'
            )

            if not is_valid:
                await self._send_invalid_screenshot_message(message, validation_reason)
                logger.warning(f"Invalid screenshot rejected: {username} ({discord_id}) - {validation_reason}")
                return

            # Log the submission
            self.db.log_submission(discord_id, image_url, filename)

            # Get updated stats
            stats = self.db.get_player_stats(discord_id)

            # Send confirmation message
            await self._send_confirmation_message(message, stats)

            logger.info(f"Submission logged: {username} ({discord_id}) - Daily: {stats['daily_count']}, Weekly: {stats['weekly_count']}")

        except Exception as e:
            logger.error(f"Error processing submission: {e}")
            await message.add_reaction('❌')
            await message.channel.send(
                f"{message.author.mention} There was an error processing your submission. Please try again later."
            )

    async def _send_confirmation_message(self, message: discord.Message, stats: dict):
        """
        Send a confirmation message after successful submission.

        Args:
            message: The Discord message object
            stats: Player statistics dictionary
        """
        embed = discord.Embed(
            title="Training Logged!",
            description=f"Great work, {message.author.mention}!",
            color=discord.Color.green()
        )
        embed.add_field(name="Daily Count", value=f"{stats['daily_count']}", inline=True)
        embed.add_field(name="Weekly Count", value=f"{stats['weekly_count']}", inline=True)
        embed.set_thumbnail(url=message.author.avatar.url if message.author.avatar else None)

        await message.add_reaction('✅')
        await message.channel.send(embed=embed)

    async def _send_duplicate_file_message(self, message: discord.Message, filename: str):
        """
        Send a message indicating the file has already been submitted.

        Args:
            message: The Discord message object
            filename: The duplicate filename
        """
        embed = discord.Embed(
            title="⚠️ Duplicate File Detected",
            description=f"{message.author.mention}, you've already uploaded this file!",
            color=discord.Color.orange()
        )
        embed.add_field(
            name="Filename",
            value=f"`{filename}`",
            inline=False
        )
        embed.set_footer(text="Duplicate prevention active")

        await message.add_reaction('⚠️')
        await message.channel.send(embed=embed)

    async def _send_invalid_screenshot_message(self, message: discord.Message, reason: str):
        """
        Send a message indicating the screenshot was rejected.

        Args:
            message: The Discord message object
            reason: Reason for rejection
        """
        embed = discord.Embed(
            title="❌ Invalid Screenshot",
            description=f"{message.author.mention}, your submission was not accepted.",
            color=discord.Color.red()
        )
        embed.add_field(
            name="Reason",
            value=reason,
            inline=False
        )
        embed.set_footer(text="Submit a valid screenshot")

        await message.add_reaction('❌')
        await message.channel.send(embed=embed)


async def setup(bot):
    """Load the MessageHandler cog."""
    await bot.add_cog(MessageHandler(bot))
