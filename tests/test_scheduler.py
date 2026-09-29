"""
Tests for handlers/scheduler.py: monthly recap and job registration.
No Discord connection is made.
"""

import asyncio
from datetime import date
from types import SimpleNamespace

from handlers.scheduler import (
    build_monthly_recap_embed,
    build_scheduler,
    monthly_recap_job,
    previous_month,
    weekly_reset_job,
)

CONFIG = {'daily_reset_hour': 0, 'weekly_reset_day': 6, 'weekly_reset_hour': 0}


class FakeChannel:
    def __init__(self):
        self.sent = []

    async def send(self, **kwargs):
        self.sent.append(kwargs)


class FakeDb:
    def __init__(self, summary=None):
        self.summary = summary or {'players': [], 'daily': [], 'months': []}
        self.calls = []

    def monthly_summary(self, year, month):
        self.calls.append(('monthly_summary', year, month))
        return self.summary

    def get_leaderboard(self):
        self.calls.append(('get_leaderboard',))
        return [{'rank': 1, 'discord_id': 'u1', 'username': 'A', 'daily_count': 1, 'weekly_count': 3}]

    def reset_weekly_counters(self):
        self.calls.append(('reset_weekly_counters',))


def fake_bot(db=None):
    channel = FakeChannel()
    return SimpleNamespace(
        config=CONFIG,
        timezone='America/New_York',
        tracking_channel_id=123,
        db=db or FakeDb(),
        get_channel=lambda _id: channel,
        channel=channel,
    )


class TestPreviousMonth:
    def test_mid_year(self):
        assert previous_month(date(2026, 10, 1)) == (2026, 9)

    def test_january_goes_to_december(self):
        assert previous_month(date(2027, 1, 1)) == (2026, 12)


class TestMonthlyRecapEmbed:
    def test_lines_match_weekly_format(self):
        players = [
            {'username': 'Alpha', 'sessions': 12, 'days_trained': 9},
            {'username': 'Bravo', 'sessions': 4, 'days_trained': 4},
        ]
        embed = build_monthly_recap_embed(players)

        assert embed.title == "Monthly Recap"
        assert embed.description == (
            "`1.` **Alpha** - 12 sessions\n"
            "`2.` **Bravo** - 4 sessions"
        )

    def test_empty_month(self):
        embed = build_monthly_recap_embed([])
        assert embed.description == "No submissions this month."


class TestJobs:
    def test_monthly_job_registered(self):
        scheduler = build_scheduler(fake_bot())
        job = scheduler.get_job('monthly_recap')

        assert job is not None
        fields = {f.name: str(f) for f in job.trigger.fields}
        assert fields['day'] == '1'
        assert fields['hour'] == '0'
        assert fields['minute'] == '0'
        assert str(job.trigger.timezone) == 'America/New_York'

    def test_daily_and_weekly_jobs_still_registered(self):
        ids = {j.id for j in build_scheduler(fake_bot()).get_jobs()}
        assert {'daily_reset', 'weekly_reset', 'monthly_recap'} <= ids

    def test_weekly_job_resets_without_posting(self):
        bot = fake_bot()
        asyncio.run(weekly_reset_job(bot))

        assert bot.channel.sent == []
        assert ('reset_weekly_counters',) in bot.db.calls

    def test_monthly_job_posts_previous_month(self):
        db = FakeDb({'players': [{'username': 'Alpha', 'sessions': 2, 'days_trained': 2}],
                     'daily': [], 'months': ['2026-09']})
        bot = fake_bot(db)

        asyncio.run(monthly_recap_job(bot, today=date(2026, 10, 1)))

        assert db.calls == [('monthly_summary', 2026, 9)]
        assert len(bot.channel.sent) == 1
        embed = bot.channel.sent[0]['embed']
        assert embed.title == "Monthly Recap"
        assert embed.description == "`1.` **Alpha** - 2 sessions"
