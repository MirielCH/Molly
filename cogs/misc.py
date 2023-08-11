# misc.py

import discord
from discord.ext import commands
from discord.commands import slash_command, Option

from content import misc


class MiscCog(commands.Cog):
    """Cog with miscellaneous commands"""
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # Commands
    @slash_command(description='A basic calculator for your mathematical needs')
    async def calculator(
        self,
        ctx: discord.ApplicationContext,
        calculation: Option(str, 'The calculation you want solved')
        ) -> None:
        """Basic calculator"""
        await misc.command_calculator(ctx, calculation)


# Initialization
def setup(bot):
    bot.add_cog(MiscCog(bot))