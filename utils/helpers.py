"""
Helper utility functions for the Discord Aim Training Tracker Bot.
"""

from datetime import datetime, date
from typing import Optional
import pytz


def get_current_date(timezone_str: str = 'UTC') -> date:
    """
    Get the current date in the specified timezone.

    Args:
        timezone_str: Timezone string (e.g., 'America/New_York')

    Returns:
        Current date in the specified timezone
    """
    tz = pytz.timezone(timezone_str)
    return datetime.now(tz).date()


def get_current_datetime(timezone_str: str = 'UTC') -> datetime:
    """
    Get the current datetime in the specified timezone.

    Args:
        timezone_str: Timezone string (e.g., 'America/New_York')

    Returns:
        Current datetime in the specified timezone
    """
    tz = pytz.timezone(timezone_str)
    return datetime.now(tz)


def format_datetime(dt: datetime, timezone_str: str = 'UTC', format_str: str = '%Y-%m-%d %H:%M:%S') -> str:
    """
    Format a datetime object to a string in the specified timezone.

    Args:
        dt: Datetime object to format
        timezone_str: Timezone string
        format_str: Format string (default: '%Y-%m-%d %H:%M:%S')

    Returns:
        Formatted datetime string
    """
    tz = pytz.timezone(timezone_str)
    if dt.tzinfo is None:
        dt = tz.localize(dt)
    else:
        dt = dt.astimezone(tz)
    return dt.strftime(format_str)


def is_valid_image_url(url: str) -> bool:
    """
    Check if a URL appears to be a valid image URL.

    Args:
        url: URL to check

    Returns:
        True if URL appears to be an image, False otherwise
    """
    if not url:
        return False

    image_extensions = ['.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp']
    url_lower = url.lower()
    return any(url_lower.endswith(ext) or ext in url_lower for ext in image_extensions)


def get_ordinal_suffix(n: int) -> str:
    """
    Get the ordinal suffix for a number (st, nd, rd, th).

    Args:
        n: The number

    Returns:
        Ordinal suffix string
    """
    if 10 <= n % 100 <= 20:
        suffix = 'th'
    else:
        suffix = {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')
    return f"{n}{suffix}"


def format_count_message(count: int, singular: str = "time", plural: str = "times") -> str:
    """
    Format a count message with proper pluralization.

    Args:
        count: The count number
        singular: Singular form of the word
        plural: Plural form of the word

    Returns:
        Formatted count message
    """
    if count == 1:
        return f"{count} {singular}"
    return f"{count} {plural}"


def validate_discord_id(discord_id: str) -> bool:
    """
    Validate a Discord ID format.

    Args:
        discord_id: Discord ID to validate

    Returns:
        True if valid, False otherwise
    """
    if not discord_id:
        return False
    return discord_id.isdigit() and len(discord_id) >= 17 and len(discord_id) <= 19


def truncate_string(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """
    Truncate a string to a maximum length.

    Args:
        text: Text to truncate
        max_length: Maximum length
        suffix: Suffix to add if truncated

    Returns:
        Truncated string
    """
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix


def get_week_number(dt: Optional[datetime] = None, timezone_str: str = 'UTC') -> int:
    """
    Get the ISO week number for a given datetime.

    Args:
        dt: Datetime object (default: current datetime)
        timezone_str: Timezone string

    Returns:
        ISO week number
    """
    if dt is None:
        dt = get_current_datetime(timezone_str)
    return dt.isocalendar()[1]


def seconds_until_next_reset(reset_hour: int = 0, timezone_str: str = 'UTC') -> int:
    """
    Calculate seconds until the next reset time.

    Args:
        reset_hour: Hour of day for reset (0-23)
        timezone_str: Timezone string

    Returns:
        Number of seconds until next reset
    """
    tz = pytz.timezone(timezone_str)
    now = datetime.now(tz)

    # Calculate next reset time
    next_reset = now.replace(hour=reset_hour, minute=0, second=0, microsecond=0)

    # If reset time has passed today, move to tomorrow
    if now >= next_reset:
        from datetime import timedelta
        next_reset += timedelta(days=1)

    return int((next_reset - now).total_seconds())
