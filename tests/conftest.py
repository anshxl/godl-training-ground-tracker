"""
Pytest configuration and fixtures for Discord Aim Training Tracker Bot tests.
"""

import pytest
import tempfile
import os
from pathlib import Path
from database import Database


@pytest.fixture
def temp_db():
    """
    Create a temporary database for testing.

    Yields:
        Database: A database instance with a temporary file
    """
    # Create a temporary file for the database
    temp_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.db')
    temp_file.close()
    db_path = temp_file.name

    # Initialize database
    db = Database(db_path)

    yield db

    # Cleanup
    db.close()
    if os.path.exists(db_path):
        os.unlink(db_path)


@pytest.fixture
def db_with_players(temp_db):
    """
    Create a database with sample players for testing.

    Args:
        temp_db: The temporary database fixture

    Returns:
        Database: Database with pre-populated test players
    """
    # Add test players
    temp_db.add_or_update_player("user1", "TestPlayer1")
    temp_db.add_or_update_player("user2", "TestPlayer2")
    temp_db.add_or_update_player("user3", "TestPlayer3")

    return temp_db


@pytest.fixture
def db_with_submissions(db_with_players):
    """
    Create a database with sample submissions for testing.

    Args:
        db_with_players: Database with players

    Returns:
        Database: Database with submissions
    """
    # Add submissions for different players
    db_with_players.log_submission("user1", "https://example.com/img1.png", "img1.png")
    db_with_players.log_submission("user2", "https://example.com/img2.png", "img2.png")
    db_with_players.log_submission("user3", "https://example.com/img4.png", "img4.png")

    return db_with_players
