"""
Scheduler for automated counter resets.
Handles daily and weekly reset jobs and the monthly recap using APScheduler.
"""

import logging
from datetime import date, datetime
from typing import Optional

import discord
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz

logger = logging.getLogger(__name__)


def setup_scheduler(bot):
    """
    Set up and start the scheduler for automated resets and the monthly recap.

    Args:
        bot: The bot instance
    """
    scheduler = build_scheduler(bot)

    # Start the scheduler
    scheduler.start()
    logger.info(f"Scheduler started with timezone: {bot.timezone}")
    logger.info(f"Daily reset scheduled for {bot.config['daily_reset_hour']}:00")
    logger.info(f"Weekly reset scheduled for day {bot.config['weekly_reset_day']} at {bot.config['weekly_reset_hour']}:00")
    logger.info("Monthly recap scheduled for day 1 at 00:00")

    # Store scheduler reference in bot for potential cleanup
    bot.scheduler = scheduler


def build_scheduler(bot) -> AsyncIOScheduler:
    """
    Build an unstarted scheduler with all jobs registered.

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

    # Monthly recap job - runs on the 1st at midnight, posts the previous month
    scheduler.add_job(
        monthly_recap_job,
        trigger=CronTrigger(
            day=1,
            hour=0,
            minute=0,
            timezone=timezone
        ),
        args=[bot],
        id='monthly_recap',
        name='Monthly Recap',
        replace_existing=True
    )

    return scheduler


def previous_month(today: date) -> tuple:
    """Return (year, month) of the month before the one containing today."""
    if today.month == 1:
        return today.year - 1, 12
    return today.year, today.month - 1


def build_monthly_recap_embed(players: list) -> discord.Embed:
    """
    Build the Monthly Recap embed.

    Args:
        players: monthly_summary()['players'], already sorted by sessions desc then username
    """
    embed = discord.Embed(
        title="Monthly Recap",
        color=discord.Color.blue()
    )
    if players:
        embed.description = "\n".join(
            f"`{rank}.` **{p['username']}** - {p['sessions']} sessions"
            for rank, p in enumerate(players, start=1)
        )
    else:
        embed.description = "No submissions this month."
    return embed


async def monthly_recap_job(bot, today: Optional[date] = None):
    """
    Job function for the monthly recap. Posts the previous month's recap.

    Args:
        bot: The bot instance
        today: Override for the current date (tests); defaults to today in bot.timezone
    """
    try:
        logger.info("Running monthly recap job...")
        if today is None:
            today = datetime.now(pytz.timezone(bot.timezone)).date()
        year, month = previous_month(today)
        summary = bot.db.monthly_summary(year, month)

        channel = bot.get_channel(bot.tracking_channel_id)
        if channel:
            await channel.send(embed=build_monthly_recap_embed(summary['players']))
            logger.info(f"Monthly recap sent for {year}-{month:02d}")

    except Exception as e:
        logger.error(f"Error in monthly recap job: {e}")


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
    The recap is posted monthly (monthly_recap_job), so this job only resets.

    Args:
        bot: The bot instance
    """
    try:
        logger.info("Running weekly reset job...")
        bot.db.reset_weekly_counters()
        logger.info("Weekly reset completed successfully")

    except Exception as e:
        logger.error(f"Error in weekly reset job: {e}")
