# clan.py
"""Contains the clan commands"""

from typing import Union

import discord
from discord.ext import commands
from discord.commands import SlashCommandGroup

from content import clan


class ClanCog(commands.Cog):
    """Cog with events and help and about commands"""
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    clan_cmd = SlashCommandGroup(
        "guild",
        "Guild commands",
    )

    # Commands
    @clan_cmd.command(name='power')
    async def clan_power(self, ctx: discord.ApplicationContext) -> None:
        """Shows the guild members with the highest top 3 power"""
        await clan.command_clan_power(self.bot, ctx)

    @commands.command(name='guild')
    @commands.bot_has_permissions(send_messages=True, embed_links=True)
    async def prefix_clan_power(self, ctx: Union[commands.Context, discord.Message]) -> None:
        """Shows the guild members with the highest top 3 power (prefix version)"""
        await clan.command_clan_power(self.bot, ctx)


# Initialization
def setup(bot):
    bot.add_cog(ClanCog(bot))