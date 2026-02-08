"""
Database module for Discord Aim Training Tracker Bot.
Handles SQLite database connection, schema creation, and all database operations.
"""

import sqlite3
import logging
from datetime import datetime, date
from typing import Optional, List, Dict, Any
import json

logger = logging.getLogger(__name__)


class Database:
    """SQLite database handler for the aim training tracker."""

    def __init__(self, db_path: str):
        """
        Initialize database connection and create tables if they don't exist.

        Args:
            db_path: Path to the SQLite database file
        """
        self.db_path = db_path
        self.conn = None
        self._connect()
        self._create_tables()

    def _connect(self):
        """Establish connection to the SQLite database."""
        try:
            self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self.conn.row_factory = sqlite3.Row  # Enable column access by name
            logger.info(f"Connected to database: {self.db_path}")
        except sqlite3.Error as e:
            logger.error(f"Database connection error: {e}")
            raise

    def _create_tables(self):
        """Create all necessary tables if they don't exist."""
        cursor = self.conn.cursor()

        try:
            # Players table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS players (
                    discord_id TEXT PRIMARY KEY,
                    username TEXT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Submissions table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS submissions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    discord_id TEXT NOT NULL,
                    submission_date DATE NOT NULL,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    image_url TEXT,
                    filename TEXT,
                    FOREIGN KEY (discord_id) REFERENCES players(discord_id)
                )
            """)

            # Counters table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS counters (
                    discord_id TEXT PRIMARY KEY,
                    daily_count INTEGER DEFAULT 0,
                    weekly_count INTEGER DEFAULT 0,
                    last_daily_reset DATETIME,
                    last_weekly_reset DATETIME,
                    FOREIGN KEY (discord_id) REFERENCES players(discord_id)
                )
            """)

            self.conn.commit()
            logger.info("Database tables created successfully")

        except sqlite3.Error as e:
            logger.error(f"Error creating tables: {e}")
            self.conn.rollback()
            raise

    # Player Management
    def add_or_update_player(self, discord_id: str, username: str):
        """
        Add a new player or update existing player's username.

        Args:
            discord_id: Discord user ID
            username: Discord username
        """
        cursor = self.conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO players (discord_id, username)
                VALUES (?, ?)
                ON CONFLICT(discord_id) DO UPDATE SET username = excluded.username
            """, (discord_id, username))

            # Initialize counter if player is new
            cursor.execute("""
                INSERT OR IGNORE INTO counters (discord_id, daily_count, weekly_count)
                VALUES (?, 0, 0)
            """, (discord_id,))

            self.conn.commit()
            logger.info(f"Player added/updated: {username} ({discord_id})")
        except sqlite3.Error as e:
            logger.error(f"Error adding/updating player: {e}")
            self.conn.rollback()
            raise

    # Submission Management
    def has_duplicate_filename(self, discord_id: str, filename: str) -> bool:
        """
        Check if a player has already submitted a file with this filename.

        Args:
            discord_id: Discord user ID
            filename: Name of the file being submitted

        Returns:
            True if filename already exists for this player, False otherwise
        """
        cursor = self.conn.cursor()

        try:
            cursor.execute("""
                SELECT COUNT(*) as count
                FROM submissions
                WHERE discord_id = ? AND filename = ?
            """, (discord_id, filename))

            result = cursor.fetchone()
            return result['count'] > 0
        except sqlite3.Error as e:
            logger.error(f"Error checking duplicate filename: {e}")
            return False

    def log_submission(self, discord_id: str, image_url: str, filename: str):
        """
        Log a new submission and increment counters.

        Args:
            discord_id: Discord user ID
            image_url: URL of the submitted image
            filename: Name of the submitted file
        """
        cursor = self.conn.cursor()
        today = date.today().isoformat()

        try:
            # Insert submission record
            cursor.execute("""
                INSERT INTO submissions (discord_id, submission_date, image_url, filename)
                VALUES (?, ?, ?, ?)
            """, (discord_id, today, image_url, filename))

            # Increment counters
            cursor.execute("""
                UPDATE counters
                SET daily_count = daily_count + 1,
                    weekly_count = weekly_count + 1
                WHERE discord_id = ?
            """, (discord_id,))

            self.conn.commit()
            logger.info(f"Submission logged for {discord_id}: {filename}")
        except sqlite3.Error as e:
            logger.error(f"Error logging submission: {e}")
            self.conn.rollback()
            raise

    # Counter Management
    def reset_daily_counters(self):
        """Reset all daily counters to 0."""
        cursor = self.conn.cursor()
        try:
            cursor.execute("""
                UPDATE counters
                SET daily_count = 0,
                    last_daily_reset = CURRENT_TIMESTAMP
            """)
            self.conn.commit()
            logger.info(f"Daily counters reset. {cursor.rowcount} players updated.")
        except sqlite3.Error as e:
            logger.error(f"Error resetting daily counters: {e}")
            self.conn.rollback()
            raise

    def reset_weekly_counters(self):
        """Reset all weekly counters to 0."""
        cursor = self.conn.cursor()
        try:
            cursor.execute("""
                UPDATE counters
                SET weekly_count = 0,
                    last_weekly_reset = CURRENT_TIMESTAMP
            """)
            self.conn.commit()
            logger.info(f"Weekly counters reset. {cursor.rowcount} players updated.")
        except sqlite3.Error as e:
            logger.error(f"Error resetting weekly counters: {e}")
            self.conn.rollback()
            raise

    # Stats and Leaderboard
    def get_player_stats(self, discord_id: str) -> Optional[Dict[str, Any]]:
        """
        Get stats for a specific player.

        Args:
            discord_id: Discord user ID

        Returns:
            Dictionary with player stats or None if player not found
        """
        cursor = self.conn.cursor()
        try:
            cursor.execute("""
                SELECT p.username, c.daily_count, c.weekly_count
                FROM players p
                JOIN counters c ON p.discord_id = c.discord_id
                WHERE p.discord_id = ?
            """, (discord_id,))

            result = cursor.fetchone()
            if result:
                return {
                    'username': result['username'],
                    'daily_count': result['daily_count'],
                    'weekly_count': result['weekly_count']
                }
            return None
        except sqlite3.Error as e:
            logger.error(f"Error getting player stats: {e}")
            return None

    def get_leaderboard(self) -> List[Dict[str, Any]]:
        """
        Get weekly leaderboard sorted by weekly_count.

        Returns:
            List of dictionaries with player stats, sorted by weekly_count descending
        """
        cursor = self.conn.cursor()
        try:
            cursor.execute("""
                SELECT p.discord_id, p.username, c.daily_count, c.weekly_count
                FROM players p
                JOIN counters c ON p.discord_id = c.discord_id
                ORDER BY c.weekly_count DESC, c.daily_count DESC
            """)

            results = cursor.fetchall()
            leaderboard = []
            for idx, row in enumerate(results, start=1):
                leaderboard.append({
                    'rank': idx,
                    'discord_id': row['discord_id'],
                    'username': row['username'],
                    'daily_count': row['daily_count'],
                    'weekly_count': row['weekly_count']
                })
            return leaderboard
        except sqlite3.Error as e:
            logger.error(f"Error getting leaderboard: {e}")
            return []

    def get_player_rank(self, discord_id: str) -> Optional[int]:
        """
        Get a player's rank on the weekly leaderboard.

        Args:
            discord_id: Discord user ID

        Returns:
            Player's rank (1-indexed) or None if not found
        """
        leaderboard = self.get_leaderboard()
        for player in leaderboard:
            if player['discord_id'] == discord_id:
                return player['rank']
        return None

    def close(self):
        """Close the database connection."""
        if self.conn:
            self.conn.close()
            logger.info("Database connection closed")

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
