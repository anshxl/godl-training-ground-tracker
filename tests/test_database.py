"""
Unit tests for database.py module.
Tests player management, submissions, counters, and leaderboard functionality.
"""

import pytest
from datetime import date


class TestPlayerManagement:
    """Tests for player-related database operations."""

    def test_add_new_player(self, temp_db):
        """Test adding a new player to the database."""
        temp_db.add_or_update_player("test_user_1", "TestUser")

        stats = temp_db.get_player_stats("test_user_1")
        assert stats is not None
        assert stats['username'] == "TestUser"
        assert stats['daily_count'] == 0
        assert stats['weekly_count'] == 0

    def test_update_existing_player(self, temp_db):
        """Test updating an existing player's username."""
        # Add player
        temp_db.add_or_update_player("test_user_1", "OldName")
        
        # Update username
        temp_db.add_or_update_player("test_user_1", "NewName")
        
        stats = temp_db.get_player_stats("test_user_1")
        assert stats['username'] == "NewName"

    def test_get_nonexistent_player_stats(self, temp_db):
        """Test getting stats for a player that doesn't exist."""
        stats = temp_db.get_player_stats("nonexistent_user")
        assert stats is None


class TestSubmissions:
    """Tests for submission-related database operations."""

    def test_log_submission(self, db_with_players):
        """Test logging a new submission."""
        db = db_with_players
        
        # Log submission
        db.log_submission("user1", "https://example.com/test.png", "test.png")
        
        # Check if submission was logged
        assert db.has_duplicate_filename("user1", "test.png") is True
        
        # Check counters were incremented
        stats = db.get_player_stats("user1")
        assert stats['daily_count'] == 1
        assert stats['weekly_count'] == 1

    def test_has_duplicate_filename_false(self, db_with_players):
        """Test that has_duplicate_filename returns False for no submissions."""
        db = db_with_players
        assert db.has_duplicate_filename("user1", "test.png") is False

    def test_has_duplicate_filename_true(self, db_with_players):
        """Test that has_duplicate_filename returns True after submission."""
        db = db_with_players
        db.log_submission("user1", "https://example.com/test.png", "test.png")
        assert db.has_duplicate_filename("user1", "test.png") is True

    def test_duplicate_filename_is_per_player(self, db_with_players):
        """Test that another player's filename does not count as a duplicate."""
        db = db_with_players
        db.log_submission("user1", "https://example.com/test.png", "test.png")
        assert db.has_duplicate_filename("user2", "test.png") is False

    def test_multiple_submissions_same_day(self, db_with_players):
        """Test that several distinct files on the same day all count."""
        db = db_with_players
        
        db.log_submission("user1", "https://example.com/test1.png", "test1.png")
        db.log_submission("user1", "https://example.com/test2.png", "test2.png")
        
        stats = db.get_player_stats("user1")
        assert stats['daily_count'] == 2
        assert stats['weekly_count'] == 2


class TestCounters:
    """Tests for counter increment and reset functionality."""

    def test_counter_increment(self, db_with_players):
        """Test that counters increment correctly."""
        db = db_with_players
        
        # Log submission
        db.log_submission("user1", "https://example.com/test.png", "test.png")
        
        stats = db.get_player_stats("user1")
        assert stats['daily_count'] == 1
        assert stats['weekly_count'] == 1

    def test_daily_reset(self, db_with_players):
        """Test daily counter reset functionality."""
        db = db_with_players
        
        # Log submissions for multiple users
        db.log_submission("user1", "https://example.com/test1.png", "test1.png")
        db.log_submission("user2", "https://example.com/test2.png", "test2.png")
        db.log_submission("user3", "https://example.com/test3.png", "test3.png")
        
        # Verify counters are set
        assert db.get_player_stats("user1")['daily_count'] == 1
        assert db.get_player_stats("user2")['daily_count'] == 1
        assert db.get_player_stats("user3")['daily_count'] == 1
        
        # Reset daily counters
        db.reset_daily_counters()
        
        # Verify daily counters are reset but weekly counters remain
        assert db.get_player_stats("user1")['daily_count'] == 0
        assert db.get_player_stats("user1")['weekly_count'] == 1
        assert db.get_player_stats("user2")['daily_count'] == 0
        assert db.get_player_stats("user2")['weekly_count'] == 1

    def test_weekly_reset(self, db_with_players):
        """Test weekly counter reset functionality."""
        db = db_with_players

        # Log submissions
        db.log_submission("user1", "https://example.com/test1.png", "test1.png")
        db.log_submission("user2", "https://example.com/test2.png", "test2.png")

        # Verify counters are set
        assert db.get_player_stats("user1")['weekly_count'] == 1
        assert db.get_player_stats("user2")['weekly_count'] == 1

        # Reset weekly counters
        db.reset_weekly_counters()

        # Verify weekly counter is reset but daily counter remains
        # (per spec: weekly reset only resets weekly_count)
        assert db.get_player_stats("user1")['daily_count'] == 1
        assert db.get_player_stats("user1")['weekly_count'] == 0
        assert db.get_player_stats("user2")['daily_count'] == 1
        assert db.get_player_stats("user2")['weekly_count'] == 0


class TestLeaderboard:
    """Tests for leaderboard functionality."""

    def test_empty_leaderboard(self, db_with_players):
        """Test leaderboard with no submissions."""
        db = db_with_players
        leaderboard = db.get_leaderboard()
        
        # Should have players but all with 0 counts
        assert len(leaderboard) == 3
        assert all(player['weekly_count'] == 0 for player in leaderboard)

    def test_leaderboard_sorting(self, db_with_players):
        """Test that leaderboard is sorted correctly by weekly count."""
        db = db_with_players
        
        # User1: 1 submission
        db.log_submission("user1", "https://example.com/test1.png", "test1.png")
        
        # User2: 2 submissions (need to simulate different days)
        # For testing purposes, we'll add multiple submissions
        db.log_submission("user2", "https://example.com/test2.png", "test2.png")
        # Reset daily to allow another submission
        db.reset_daily_counters()
        db.log_submission("user2", "https://example.com/test3.png", "test3.png")
        
        # User3: 3 submissions
        db.log_submission("user3", "https://example.com/test4.png", "test4.png")
        db.reset_daily_counters()
        db.log_submission("user3", "https://example.com/test5.png", "test5.png")
        db.reset_daily_counters()
        db.log_submission("user3", "https://example.com/test6.png", "test6.png")
        
        # Get leaderboard
        leaderboard = db.get_leaderboard()
        
        # Verify sorting (highest weekly count first)
        assert leaderboard[0]['discord_id'] == "user3"
        assert leaderboard[0]['weekly_count'] == 3
        assert leaderboard[0]['rank'] == 1
        
        assert leaderboard[1]['discord_id'] == "user2"
        assert leaderboard[1]['weekly_count'] == 2
        assert leaderboard[1]['rank'] == 2
        
        assert leaderboard[2]['discord_id'] == "user1"
        assert leaderboard[2]['weekly_count'] == 1
        assert leaderboard[2]['rank'] == 3

    def test_leaderboard_ranks(self, db_with_players):
        """Test that ranks are assigned correctly."""
        db = db_with_players
        
        # Add submissions
        db.log_submission("user1", "https://example.com/test1.png", "test1.png")
        db.log_submission("user2", "https://example.com/test2.png", "test2.png")
        db.log_submission("user3", "https://example.com/test3.png", "test3.png")
        
        leaderboard = db.get_leaderboard()
        
        # All have same count, so ranks should be 1, 2, 3
        assert leaderboard[0]['rank'] == 1
        assert leaderboard[1]['rank'] == 2
        assert leaderboard[2]['rank'] == 3

    def test_get_player_rank(self, db_with_players):
        """Test getting a specific player's rank."""
        db = db_with_players
        
        # User1: 1 submission
        db.log_submission("user1", "https://example.com/test1.png", "test1.png")
        
        # User2: 2 submissions
        db.log_submission("user2", "https://example.com/test2.png", "test2.png")
        db.reset_daily_counters()
        db.log_submission("user2", "https://example.com/test3.png", "test3.png")
        
        # User3: 0 submissions
        
        # Check ranks
        assert db.get_player_rank("user2") == 1  # Highest count
        assert db.get_player_rank("user1") == 2
        assert db.get_player_rank("user3") == 3  # Lowest count

    def test_get_rank_nonexistent_player(self, temp_db):
        """Test getting rank for a player that doesn't exist."""
        rank = temp_db.get_player_rank("nonexistent_user")
        assert rank is None

    def test_leaderboard_after_weekly_reset(self, db_with_players):
        """Test that leaderboard resets correctly after weekly reset."""
        db = db_with_players
        
        # Add submissions
        db.log_submission("user1", "https://example.com/test1.png", "test1.png")
        db.log_submission("user2", "https://example.com/test2.png", "test2.png")
        
        # Verify counts
        assert db.get_player_stats("user1")['weekly_count'] == 1
        
        # Weekly reset
        db.reset_weekly_counters()
        
        # Verify leaderboard shows all zeros
        leaderboard = db.get_leaderboard()
        assert all(player['weekly_count'] == 0 for player in leaderboard)


class TestIntegration:
    """Integration tests for complete workflows."""

    def test_weekly_cycle(self, db_with_players):
        """Test a complete weekly cycle: submissions -> reset -> new submissions."""
        db = db_with_players

        # Week 1: Add submissions
        db.log_submission("user1", "https://example.com/w1_d1.png", "w1_d1.png")
        db.reset_daily_counters()
        db.log_submission("user1", "https://example.com/w1_d2.png", "w1_d2.png")

        # Check week 1 stats
        stats_w1 = db.get_player_stats("user1")
        assert stats_w1['weekly_count'] == 2

        # Sunday midnight: both daily and weekly resets happen
        db.reset_daily_counters()
        db.reset_weekly_counters()

        # Check after reset
        stats_after_reset = db.get_player_stats("user1")
        assert stats_after_reset['daily_count'] == 0
        assert stats_after_reset['weekly_count'] == 0
        
        # Week 2: Add new submissions
        db.log_submission("user1", "https://example.com/w2_d1.png", "w2_d1.png")
        
        # Check week 2 stats
        stats_w2 = db.get_player_stats("user1")
        assert stats_w2['daily_count'] == 1
        assert stats_w2['weekly_count'] == 1

    def test_multiple_players_workflow(self, db_with_players):
        """Test workflow with multiple players submitting."""
        db = db_with_players
        
        # Day 1
        db.log_submission("user1", "https://example.com/u1_d1.png", "u1_d1.png")
        db.log_submission("user2", "https://example.com/u2_d1.png", "u2_d1.png")
        db.log_submission("user3", "https://example.com/u3_d1.png", "u3_d1.png")
        
        # Check all submitted
        assert db.has_duplicate_filename("user1", "u1_d1.png")
        assert db.has_duplicate_filename("user2", "u2_d1.png")
        assert db.has_duplicate_filename("user3", "u3_d1.png")
        
        # Daily reset
        db.reset_daily_counters()
        
        # Day 2 - only user1 and user2 submit
        db.log_submission("user1", "https://example.com/u1_d2.png", "u1_d2.png")
        db.log_submission("user2", "https://example.com/u2_d2.png", "u2_d2.png")
        
        # Check leaderboard
        leaderboard = db.get_leaderboard()
        
        # user1 and user2 should have weekly_count of 2
        user1_entry = next(p for p in leaderboard if p['discord_id'] == 'user1')
        user2_entry = next(p for p in leaderboard if p['discord_id'] == 'user2')
        user3_entry = next(p for p in leaderboard if p['discord_id'] == 'user3')
        
        assert user1_entry['weekly_count'] == 2
        assert user2_entry['weekly_count'] == 2
        assert user3_entry['weekly_count'] == 1  # Only submitted day 1
