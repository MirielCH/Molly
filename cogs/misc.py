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
        
    @slash_command(description='Shows all currently redeemable codes in IDLE FARM')
    async def codes(self, ctx: discord.ApplicationContext) -> None:
        """Codes"""
        await misc.command_codes(ctx)

    #Prefix commands
    @commands.command(name='calculator', aliases=('calc','math'))
    @commands.bot_has_permissions(send_messages=True, embed_links=True)
    async def prefix_calculator(self, ctx: commands.Context, calculation: str) -> None:
        """Basic calculator (prefix version)"""
        await misc.command_calculator(ctx, calculation)
        
    @commands.command(name='codes', aliases=('code',))
    @commands.bot_has_permissions(send_messages=True, embed_links=True)
    async def prefix_codes(self, ctx: commands.Context, *args: str) -> None:
        """Codes (prefix version)"""
        await misc.command_codes(ctx)


# Initialization
def setup(bot):
    bot.add_cog(MiscCog(bot))