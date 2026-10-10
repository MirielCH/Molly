# settings.py
"""Contains settings commands"""

import discord
from discord.commands import SlashCommandGroup, slash_command, Option
from discord.ext import commands

from database import clans
from content import settings as settings_cmd
from resources import functions


class SettingsCog(commands.Cog):
    """Cog with user settings commands"""
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # Slash commands
    @slash_command()
    async def on(self, ctx: discord.ApplicationContext) -> None:
        """Activate Molly"""
        await settings_cmd.command_on(self.bot, ctx)

    @slash_command()
    async def off(self, ctx: discord.ApplicationContext) -> None:
        """Disable Molly"""
        await settings_cmd.command_off(self.bot, ctx)

    cmd_purge = SlashCommandGroup(
        "purge",
        "Purge commands",
    )

    @cmd_purge.command()
    async def data(self, ctx: discord.ApplicationContext) -> None:
        """Purges your user data from Molly"""
        await settings_cmd.command_purge_data(self.bot, ctx)

    cmd_settings = SlashCommandGroup(
        "settings",
        "Settings commands",
    )

    @cmd_settings.command()
    async def guild(self, ctx: discord.ApplicationContext) -> None:
        """Manage guild settings"""
        await settings_cmd.command_settings_clan(self.bot, ctx)
        
    @cmd_settings.command()
    async def helpers(self, ctx: discord.ApplicationContext) -> None:
        """Manage helpers"""
        await settings_cmd.command_settings_helpers(self.bot, ctx)
        
    @cmd_settings.command()
    async def messages(self, ctx: discord.ApplicationContext) -> None:
        """Manage reminder messages"""
        await settings_cmd.command_settings_messages(self.bot, ctx)

    @cmd_settings.command()
    async def reminders(self, ctx: discord.ApplicationContext) -> None:
        """Manage reminder settings"""
        await settings_cmd.command_settings_reminders(self.bot, ctx)

    @commands.guild_only()
    @cmd_settings.command()
    async def server(self, ctx: discord.ApplicationContext) -> None:
        """Manage server settings"""
        if not ctx.author.guild_permissions.manage_guild:
            raise commands.MissingPermissions(['manage_guild',])
        await settings_cmd.command_settings_server(self.bot, ctx)

    @cmd_settings.command()
    async def user(self, ctx: discord.ApplicationContext) -> None:
        """Manage user settings"""
        await settings_cmd.command_settings_user(self.bot, ctx)


# Initialization
def setup(bot):
    bot.add_cog(SettingsCog(bot))
