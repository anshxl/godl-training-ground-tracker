"""
Stats commands for displaying player statistics and leaderboards.
"""

import logging
import discord
from discord.ext import commands

logger = logging.getLogger(__name__)


class StatsCommands(commands.Cog):
    """Commands for viewing player stats and leaderboards."""

    def __init__(self, bot):
        """
        Initialize the stats commands.

        Args:
            bot: The bot instance
        """
        self.bot = bot
        self.db = bot.db

    @commands.command(name='leaderboard', aliases=['stats', 'lb'])
    async def leaderboard(self, ctx):
        """
        Display the weekly leaderboard of all players.

        Usage: !leaderboard or !stats or !lb
        """
        try:
            leaderboard = self.db.get_leaderboard()

            if not leaderboard:
                await ctx.send("No submissions yet.")
                return

            # Create embed
            embed = discord.Embed(
                title="Weekly Leaderboard",
                # description="Top aim trainers this week",
                color=discord.Color.gold()
            )

            # Add leaderboard entries (top 10)
            leaderboard_text = []
            for player in leaderboard[:10]:
                rank = player['rank']
                username = player['username']
                daily = player['daily_count']
                weekly = player['weekly_count']

                # Medal emojis for top 3
                medal = f"`{rank}.`"
                # if rank == 1:
                #     medal = "🥇"
                # elif rank == 2:
                #     medal = "🥈"
                # elif rank == 3:
                #     medal = "🥉"
                # else:
                #     medal = f"`{rank}.`"

                leaderboard_text.append(
                    f"{medal} **{username}** - Daily: {daily} | Weekly: {weekly}"
                )

            embed.add_field(
                name="Rankings",
                value="\n".join(leaderboard_text),
                inline=False
            )

            # Add total players count
            embed.set_footer(text=f"Total players: {len(leaderboard)}")

            await ctx.send(embed=embed)
            logger.info(f"Leaderboard requested by {ctx.author.name}")

        except Exception as e:
            logger.error(f"Error displaying leaderboard: {e}")
            await ctx.send("An error occurred while fetching the leaderboard. Please try again later.")

    @commands.command(name='mystats', aliases=['me', 'myrank'])
    async def mystats(self, ctx):
        """
        Display the requesting user's current stats and rank.

        Usage: !mystats or !me or !myrank
        """
        discord_id = str(ctx.author.id)

        try:
            # Get player stats
            stats = self.db.get_player_stats(discord_id)

            if not stats:
                await ctx.send(
                    f"{ctx.author.mention}, you haven't submitted any training yet! "
                    f"Post a screenshot in <#{self.bot.tracking_channel_id}> to get started."
                )
                return

            # Get player ranks
            weekly_rank = self.db.get_player_rank(discord_id)
            alltime_stats = self.db.get_player_alltime_stats(discord_id)
            alltime_rank = self.db.get_player_alltime_rank(discord_id)

            # Create embed
            embed = discord.Embed(
                title=f"📊 Stats for {stats['username']}",
                color=discord.Color.blue()
            )

            # Weekly stats
            embed.add_field(name="Daily Count", value=f"🎯 {stats['daily_count']}", inline=True)
            embed.add_field(name="Weekly Count", value=f"📅 {stats['weekly_count']}", inline=True)
            embed.add_field(name="Weekly Rank", value=f"🏅 #{weekly_rank}", inline=True)

            # All-time stats
            if alltime_stats:
                embed.add_field(
                    name="All-Time Total",
                    value=f"🏆 {alltime_stats['total_submissions']} sessions",
                    inline=True
                )
                embed.add_field(
                    name="All-Time Rank",
                    value=f"🌟 #{alltime_rank}",
                    inline=True
                )
                embed.add_field(name="\u200b", value="\u200b", inline=True)  # Empty field for spacing

            # # Add motivational message based on rank
            # if rank == 1:
            #     motivation = "You're #1! Keep dominating! 👑"
            # elif rank <= 3:
            #     motivation = "Top 3! So close to #1! 🔥"
            # elif rank <= 5:
            #     motivation = "Top 5! Keep pushing! 💪"
            # else:
            #     motivation = "Keep training to climb the ranks! 🎯"

            # embed.add_field(name="Status", value=motivation, inline=False)

            embed.set_thumbnail(url=ctx.author.avatar.url if ctx.author.avatar else None)
            embed.set_footer(text="Consistency is key!")

            await ctx.send(embed=embed)
            logger.info(f"Stats requested by {ctx.author.name}")

        except Exception as e:
            logger.error(f"Error displaying user stats: {e}")
            await ctx.send("An error occurred while fetching your stats. Please try again later.")

    @commands.command(name='alltime', aliases=['lifetime', 'total', 'at'])
    async def alltime(self, ctx):
        """
        Display the all-time leaderboard based on total submissions.

        Usage: !alltime or !lifetime or !total or !at
        """
        try:
            leaderboard = self.db.get_alltime_leaderboard()

            if not leaderboard:
                await ctx.send("No submissions yet.")
                return

            # Filter out players with 0 submissions
            active_players = [p for p in leaderboard if p['total_submissions'] > 0]

            if not active_players:
                await ctx.send("No submissions yet.")
                return

            # Create embed
            embed = discord.Embed(
                title="All-Time Leaderboard",
                description="Total submissions since the beginning",
                color=discord.Color.purple()
            )

            # Add leaderboard entries (top 10)
            leaderboard_text = []
            for player in active_players[:10]:
                rank = player['rank']
                username = player['username']
                total = player['total_submissions']

                # Medal emojis for top 3
                # medal = ""
                # if rank == 1:
                #     medal = "🥇"
                # elif rank == 2:
                #     medal = "🥈"
                # elif rank == 3:
                #     medal = "🥉"
                # else:
                medal = f"`{rank}.`"

                leaderboard_text.append(
                    f"{medal} **{username}** - {total} sessions"
                )

            embed.add_field(
                name="Rankings",
                value="\n".join(leaderboard_text),
                inline=False
            )

            # Add total players count
            embed.set_footer(text=f"Total active players: {len(active_players)}")

            await ctx.send(embed=embed)
            logger.info(f"All-time leaderboard requested by {ctx.author.name}")

        except Exception as e:
            logger.error(f"Error displaying all-time leaderboard: {e}")
            await ctx.send("An error occurred while fetching the all-time leaderboard. Please try again later.")


async def setup(bot):
    """Load the StatsCommands cog."""
    await bot.add_cog(StatsCommands(bot))
