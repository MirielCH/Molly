# clan.py
"""Contains the clan commands"""

from typing import Union

import discord
from discord.ext import commands
from discord.commands import Option, SlashCommandGroup

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
    @clan_cmd.command(name='members')
    async def clan_members(
        self,
        ctx: discord.ApplicationContext,
        view: Option(str, 'The view you want to see', choices=['Top 3 power', 'Guild seals'], default=None),
    ) -> None:
        """Shows the guild members with the highest top 3 power"""
        current_view = 0
        if view is not None:
            if 'seal' in view.lower():
                current_view = 1
        await clan.command_clan_members(self.bot, ctx, current_view)

    @commands.command(name='guild', aliases=('clan',))
    @commands.bot_has_permissions(send_messages=True, embed_links=True)
    async def prefix_clan_members(self, ctx: Union[commands.Context, discord.Message], *args: str) -> None:
        """Shows the clan members with the highest top 3 power (prefix version)"""
        arguments = ' '.join(args).lower() if args else ''
        current_view = 0
        strings_guild_seals = [
            'seal',
            'contribut',
            'inv',
        ]
        if any(string in arguments for string in strings_guild_seals):
            current_view = 1
        await clan.command_clan_members(self.bot, ctx, current_view)


# Initialization
def setup(bot):
    bot.add_cog(ClanCog(bot))