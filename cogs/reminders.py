# reminders.py
"""Contains reminder commands"""

import discord
from discord.commands import SlashCommandGroup, Option
from discord.ext import commands

from content import reminders_lists, reminders_custom
from resources import functions


class RemindersCog(commands.Cog):
    """Cog with reminders commands"""
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    cmd_reminders = SlashCommandGroup(
        "reminders",
        "Reminder commands",
    )

    @cmd_reminders.command(name='add')
    async def reminders_add(
        self,
        ctx: discord.ApplicationContext,
        timestring: Option(str, 'Timestring (e.g. 1h20m10s'),
        text: Option(str, 'Text of the reminder', max_length=150),
    ) -> None:
        """Adds a custom reminder"""
        await reminders_custom.command_custom_reminder(ctx, timestring, text)

    @cmd_reminders.command(name='list')
    async def reminders_list(
        self,
        ctx: discord.ApplicationContext,
        user: Option(discord.User, 'User you want to check commands for', default=None),
    ) -> None:
        """Lists your commands and active reminders"""
        await reminders_lists.command_list(self.bot, ctx, user)

# Initialization
def setup(bot):
    bot.add_cog(RemindersCog(bot))