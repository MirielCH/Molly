# workers.py
"""Contains the worker commands"""

from typing import Union

import discord
from discord.ext import commands
from discord.commands import slash_command

from content import workers


class WorkersCog(commands.Cog):
    """Cog with events and help and about commands"""
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # Commands
    @slash_command(name='workers')
    async def workers_list(self, ctx: discord.ApplicationContext) -> None:
        """Shows all currently stored workers and their power"""
        await workers.command_workers_list(self.bot, ctx)

    @commands.command(name='workers', aliases=('worker','wo'))
    @commands.bot_has_permissions(send_messages=True, embed_links=True)
    async def prefix_workers_list(self, ctx: Union[commands.Context, discord.Message]) -> None:
        """Workers list command (prefix version)"""
        await workers.command_workers_list(self.bot, ctx)


# Initialization
def setup(bot):
    bot.add_cog(WorkersCog(bot))