"""
Admin commands for managing the tracker bot.
"""

import logging
import discord
from discord.ext import commands

logger = logging.getLogger(__name__)


class AdminCommands(commands.Cog):
    """Admin-only commands for bot management."""

    def __init__(self, bot):
        """
        Initialize the admin commands.

        Args:
            bot: The bot instance
        """
        self.bot = bot
        self.db = bot.db
        self.admin_role_id = bot.admin_role_id

    def _is_admin(self, ctx) -> bool:
        """
        Check if the user has admin permissions.

        Args:
            ctx: Command context

        Returns:
            True if user is admin, False otherwise
        """
        # Check if user has the admin role
        if hasattr(ctx.author, 'roles'):
            for role in ctx.author.roles:
                if role.id == self.admin_role_id:
                    return True

        # Check if user has administrator permission
        if ctx.author.guild_permissions.administrator:
            return True

        return False

    @commands.group(name='admin', invoke_without_command=True)
    async def admin(self, ctx):
        """
        Admin command group.

        Usage: !admin <subcommand>
        """
        if not self._is_admin(ctx):
            await ctx.send("❌ You don't have permission to use admin commands.")
            return

        # Show available admin commands
        embed = discord.Embed(
            title="🔧 Admin Commands",
            description="Available admin commands:",
            color=discord.Color.red()
        )
        embed.add_field(
            name="!admin reset daily",
            value="Manually reset all daily counters to 0",
            inline=False
        )
        embed.add_field(
            name="!admin reset weekly",
            value="Manually reset all weekly counters to 0",
            inline=False
        )
        embed.add_field(
            name="!admin set @user daily <number>",
            value="Set a player's daily counter to a specific value",
            inline=False
        )
        embed.add_field(
            name="!admin set @user weekly <number>",
            value="Set a player's weekly counter to a specific value",
            inline=False
        )
        embed.add_field(
            name="!admin add @user daily <number>",
            value="Add to a player's daily counter (use negative to subtract)",
            inline=False
        )
        embed.add_field(
            name="!admin add @user weekly <number>",
            value="Add to a player's weekly counter (use negative to subtract)",
            inline=False
        )
        embed.add_field(
            name="!admin info",
            value="Display bot configuration information",
            inline=False
        )
        embed.set_footer(text="Use these commands with caution!")

        await ctx.send(embed=embed)

    @admin.group(name='reset', invoke_without_command=True)
    async def reset(self, ctx):
        """
        Reset command group.

        Usage: !admin reset <daily|weekly>
        """
        if not self._is_admin(ctx):
            await ctx.send("❌ You don't have permission to use admin commands.")
            return

        await ctx.send(
            "Please specify what to reset:\n"
            "• `!admin reset daily` - Reset daily counters\n"
            "• `!admin reset weekly` - Reset weekly counters"
        )

    @reset.command(name='daily')
    async def reset_daily(self, ctx):
        """
        Manually reset all daily counters.

        Usage: !admin reset daily
        """
        if not self._is_admin(ctx):
            await ctx.send("❌ You don't have permission to use admin commands.")
            return

        try:
            # Confirm action
            confirm_embed = discord.Embed(
                title="⚠️ Confirm Reset",
                description="Are you sure you want to reset all daily counters?\nReact with ✅ to confirm or ❌ to cancel.",
                color=discord.Color.orange()
            )
            confirm_msg = await ctx.send(embed=confirm_embed)
            await confirm_msg.add_reaction('✅')
            await confirm_msg.add_reaction('❌')

            # Wait for reaction
            def check(reaction, user):
                return user == ctx.author and str(reaction.emoji) in ['✅', '❌'] and reaction.message.id == confirm_msg.id

            reaction, user = await self.bot.wait_for('reaction_add', timeout=30.0, check=check)

            if str(reaction.emoji) == '✅':
                # Perform reset
                self.db.reset_daily_counters()

                embed = discord.Embed(
                    title="✅ Daily Counters Reset",
                    description="All daily counters have been reset to 0.",
                    color=discord.Color.green()
                )
                await ctx.send(embed=embed)
                logger.info(f"Daily counters manually reset by {ctx.author.name}")
            else:
                await ctx.send("Reset cancelled.")

        except TimeoutError:
            await ctx.send("Reset cancelled due to timeout.")
        except Exception as e:
            logger.error(f"Error resetting daily counters: {e}")
            await ctx.send("An error occurred while resetting daily counters.")

    @reset.command(name='weekly')
    async def reset_weekly(self, ctx):
        """
        Manually reset all weekly counters.

        Usage: !admin reset weekly
        """
        if not self._is_admin(ctx):
            await ctx.send("❌ You don't have permission to use admin commands.")
            return

        try:
            # Confirm action
            confirm_embed = discord.Embed(
                title="⚠️ Confirm Reset",
                description="Are you sure you want to reset all weekly counters?\nReact with ✅ to confirm or ❌ to cancel.",
                color=discord.Color.orange()
            )
            confirm_msg = await ctx.send(embed=confirm_embed)
            await confirm_msg.add_reaction('✅')
            await confirm_msg.add_reaction('❌')

            # Wait for reaction
            def check(reaction, user):
                return user == ctx.author and str(reaction.emoji) in ['✅', '❌'] and reaction.message.id == confirm_msg.id

            reaction, user = await self.bot.wait_for('reaction_add', timeout=30.0, check=check)

            if str(reaction.emoji) == '✅':
                # Perform reset
                self.db.reset_weekly_counters()

                embed = discord.Embed(
                    title="✅ Weekly Counters Reset",
                    description="All weekly counters have been reset to 0.",
                    color=discord.Color.green()
                )
                await ctx.send(embed=embed)
                logger.info(f"Weekly counters manually reset by {ctx.author.name}")
            else:
                await ctx.send("Reset cancelled.")

        except TimeoutError:
            await ctx.send("Reset cancelled due to timeout.")
        except Exception as e:
            logger.error(f"Error resetting weekly counters: {e}")
            await ctx.send("An error occurred while resetting weekly counters.")

    @admin.group(name='set', invoke_without_command=True)
    async def set_counter(self, ctx, member: discord.Member = None, counter_type: str = None, value: int = None):
        """
        Set a player's counter to a specific value.

        Usage: !admin set @user <daily|weekly> <number>
        """
        if not self._is_admin(ctx):
            await ctx.send("❌ You don't have permission to use admin commands.")
            return

        if not member or not counter_type or value is None:
            await ctx.send(
                "❌ Invalid usage. Correct format:\n"
                "`!admin set @user daily <number>` or `!admin set @user weekly <number>`"
            )
            return

        if counter_type not in ['daily', 'weekly']:
            await ctx.send("❌ Counter type must be 'daily' or 'weekly'")
            return

        if value < 0:
            await ctx.send("❌ Value cannot be negative")
            return

        try:
            discord_id = str(member.id)
            username = member.display_name

            # Ensure player exists
            self.db.add_or_update_player(discord_id, username)

            # Set the counter
            self.db.set_player_counter(discord_id, counter_type, value)

            embed = discord.Embed(
                title="✅ Counter Updated",
                description=f"Set **{member.mention}**'s {counter_type} counter to **{value}**",
                color=discord.Color.green()
            )
            await ctx.send(embed=embed)
            logger.info(f"Admin {ctx.author.name} set {member.display_name}'s {counter_type} counter to {value}")

        except ValueError as e:
            await ctx.send(f"❌ Error: {str(e)}")
        except Exception as e:
            logger.error(f"Error setting counter: {e}")
            await ctx.send("❌ An error occurred while updating the counter.")

    @admin.group(name='add', invoke_without_command=True)
    async def add_counter(self, ctx, member: discord.Member = None, counter_type: str = None, adjustment: int = None):
        """
        Add to a player's counter (use negative to subtract).

        Usage: !admin add @user <daily|weekly> <number>
        """
        if not self._is_admin(ctx):
            await ctx.send("❌ You don't have permission to use admin commands.")
            return

        if not member or not counter_type or adjustment is None:
            await ctx.send(
                "❌ Invalid usage. Correct format:\n"
                "`!admin add @user daily <number>` or `!admin add @user weekly <number>`\n"
                "Use negative numbers to subtract (e.g., -1)"
            )
            return

        if counter_type not in ['daily', 'weekly']:
            await ctx.send("❌ Counter type must be 'daily' or 'weekly'")
            return

        try:
            discord_id = str(member.id)
            username = member.display_name

            # Ensure player exists
            self.db.add_or_update_player(discord_id, username)

            # Adjust the counter
            self.db.adjust_player_counter(discord_id, counter_type, adjustment)

            # Get new stats
            stats = self.db.get_player_stats(discord_id)
            new_value = stats['daily_count'] if counter_type == 'daily' else stats['weekly_count']

            action = "Added" if adjustment >= 0 else "Subtracted"
            embed = discord.Embed(
                title="✅ Counter Updated",
                description=f"{action} **{abs(adjustment)}** to **{member.mention}**'s {counter_type} counter\nNew value: **{new_value}**",
                color=discord.Color.green()
            )
            await ctx.send(embed=embed)
            logger.info(f"Admin {ctx.author.name} adjusted {member.display_name}'s {counter_type} counter by {adjustment}")

        except ValueError as e:
            await ctx.send(f"❌ Error: {str(e)}")
        except Exception as e:
            logger.error(f"Error adjusting counter: {e}")
            await ctx.send("❌ An error occurred while updating the counter.")

    @admin.command(name='info')
    async def info(self, ctx):
        """
        Display bot configuration information.

        Usage: !admin info
        """
        if not self._is_admin(ctx):
            await ctx.send("❌ You don't have permission to use admin commands.")
            return

        embed = discord.Embed(
            title="🤖 Bot Configuration",
            color=discord.Color.blue()
        )
        embed.add_field(name="Bot Name", value=self.bot.user.name, inline=True)
        embed.add_field(name="Bot ID", value=self.bot.user.id, inline=True)
        embed.add_field(name="Tracking Channel", value=f"<#{self.bot.tracking_channel_id}>", inline=True)
        embed.add_field(name="Database", value=self.bot.config['database_path'], inline=True)
        embed.add_field(name="Timezone", value=self.bot.timezone, inline=True)
        embed.add_field(name="Prefix", value=self.bot.config['prefix'], inline=True)
        embed.add_field(
            name="Reset Schedule",
            value=f"Daily: {self.bot.config['daily_reset_hour']}:00\nWeekly: Day {self.bot.config['weekly_reset_day']}, {self.bot.config['weekly_reset_hour']}:00",
            inline=False
        )

        await ctx.send(embed=embed)


async def setup(bot):
    """Load the AdminCommands cog."""
    await bot.add_cog(AdminCommands(bot))
