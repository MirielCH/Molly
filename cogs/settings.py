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

    #Prefix commands
    @commands.command(name='on', aliases=('register', 'activate', 'start'))
    @commands.bot_has_permissions(send_messages=True, embed_links=True)
    async def prefix_on(self, ctx: commands.Context, *args: str) -> None:
        """Turn on Navi (prefix version)"""
        await ctx.reply(f'Yeehaw! Please use {await functions.get_bot_slash_command(self.bot, "on")} to activate me.')

    @commands.command(name='off', aliases=('deactivate','stop'))
    @commands.bot_has_permissions(send_messages=True, embed_links=True)
    async def prefix_off(self, ctx: commands.Context, *args: str) -> None:
        """Turn off Navi (prefix version)"""
        await ctx.reply(f'Yeehaw! Please use {await functions.get_bot_slash_command(self.bot, "off")} to deactivate me.')

    @commands.command(name='settings', aliases=('me','setting','set'))
    @commands.bot_has_permissions(send_messages=True, embed_links=True)
    async def prefix_settings(self, ctx: commands.Context, *args: str) -> None:
        """Settings (prefix version)"""
        await ctx.reply(
            f'➜ {await functions.get_bot_slash_command(self.bot, "settings guild")}\n'
            f'➜ {await functions.get_bot_slash_command(self.bot, "settings helpers")}\n'
            f'➜ {await functions.get_bot_slash_command(self.bot, "settings messages")}\n'
            f'➜ {await functions.get_bot_slash_command(self.bot, "settings reminders")}\n'
            f'➜ {await functions.get_bot_slash_command(self.bot, "settings server")}\n'
            f'➜ {await functions.get_bot_slash_command(self.bot, "settings user")}\n'
        )


# Initialization
def setup(bot):
    bot.add_cog(SettingsCog(bot))
