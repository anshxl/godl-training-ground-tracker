"""
Scheduler for automated counter resets.
Handles daily and weekly reset jobs using APScheduler.
"""

import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz

logger = logging.getLogger(__name__)


def setup_scheduler(bot):
    """
    Set up the scheduler for automated counter resets.

    Args:
        bot: The bot instance
    """
    scheduler = AsyncIOScheduler()

    # Get configuration
    timezone = pytz.timezone(bot.timezone)
    daily_reset_hour = bot.config['daily_reset_hour']
    weekly_reset_day = bot.config['weekly_reset_day']  # 6 = Sunday
    weekly_reset_hour = bot.config['weekly_reset_hour']

    # Daily reset job - runs every day at specified hour
    scheduler.add_job(
        daily_reset_job,
        trigger=CronTrigger(
            hour=daily_reset_hour,
            minute=0,
            timezone=timezone
        ),
        args=[bot],
        id='daily_reset',
        name='Daily Counter Reset',
        replace_existing=True
    )

    # Weekly reset job - runs every Sunday (or configured day) at specified hour
    scheduler.add_job(
        weekly_reset_job,
        trigger=CronTrigger(
            day_of_week=weekly_reset_day,
            hour=weekly_reset_hour,
            minute=0,
            timezone=timezone
        ),
        args=[bot],
        id='weekly_reset',
        name='Weekly Counter Reset',
        replace_existing=True
    )

    # Start the scheduler
    scheduler.start()
    logger.info(f"Scheduler started with timezone: {bot.timezone}")
    logger.info(f"Daily reset scheduled for {daily_reset_hour}:00")
    logger.info(f"Weekly reset scheduled for day {weekly_reset_day} at {weekly_reset_hour}:00")

    # Store scheduler reference in bot for potential cleanup
    bot.scheduler = scheduler


async def daily_reset_job(bot):
    """
    Job function for daily counter reset.

    Args:
        bot: The bot instance
    """
    try:
        logger.info("Running daily reset job...")
        bot.db.reset_daily_counters()
        logger.info("Daily reset completed successfully")

    except Exception as e:
        logger.error(f"Error in daily reset job: {e}")


async def weekly_reset_job(bot):
    """
    Job function for weekly counter reset.
    Sends weekly leaderboard before resetting counters.

    Args:
        bot: The bot instance
    """
    try:
        logger.info("Running weekly reset job...")

        # Get leaderboard BEFORE resetting
        leaderboard = bot.db.get_leaderboard()

        # Send weekly leaderboard message
        try:
            channel = bot.get_channel(bot.tracking_channel_id)
            if channel:
                import discord

                embed = discord.Embed(
                    title="Weekly Recap",
                    color=discord.Color.blue()
                )

                if leaderboard:
                    # Filter out players with 0 sessions
                    active_players = [p for p in leaderboard if p['weekly_count'] > 0]

                    if active_players:
                        leaderboard_text = []
                        for player in active_players:
                            rank = player['rank']
                            username = player['username']
                            weekly = player['weekly_count']
                            leaderboard_text.append(f"`{rank}.` **{username}** - {weekly} sessions")

                        embed.description = "\n".join(leaderboard_text)
                    else:
                        embed.description = "No submissions this week."

                await channel.send(embed=embed)
                logger.info("Weekly leaderboard message sent")

        except Exception as e:
            logger.error(f"Error sending weekly leaderboard message: {e}")

        # Now reset the counters
        bot.db.reset_weekly_counters()
        logger.info("Weekly reset completed successfully")

    except Exception as e:
        logger.error(f"Error in weekly reset job: {e}")
