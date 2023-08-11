# tracking.py
"""Contains commands related to command tracking"""

import re

import discord
from discord.commands import slash_command, Option
from discord.ext import commands

from content import tracking as tracking_cmd


class TrackingCog(commands.Cog):
    """Cog with command tracking commands"""
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # Commands
    @slash_command()
    async def stats(
        self,
        ctx: discord.ApplicationContext,
        timestring: Option(str, 'The relative timeframe you want stats for. Example: 1d5h30m.', default=None),
        user: Option(discord.User, 'User to view the stats of. Shows your own stats it empty.', default=None),
    ) -> None:
        """Lists your command statistics"""
        await tracking_cmd.command_stats(self.bot, ctx, timestring, user)

    @commands.command(name='stats', aliases=('stat','st','statistic', 'statistics'))
    @commands.bot_has_permissions(send_messages=True, embed_links=True)
    async def prefix_stats(self, ctx: commands.Context, *args: str) -> None:
        """Lists all stats (prefix version)"""
        user = None
        for mentioned_user in ctx.message.mentions.copy():
            if mentioned_user == self.bot.user:
                ctx.message.mentions.remove(mentioned_user)
                break
        if ctx.message.mentions:
            user = ctx.message.mentions[0]
            if user.bot:
                await ctx.reply('Imagine trying to check the reminders of a bot.')
                return
        args = ''.join(args)
        timestring = re.sub(r'<@!?[0-9]+>', '', args.lower())
        if timestring == '': timestring = None
        await tracking_cmd.command_stats(self.bot, ctx, timestring, user)
        

# Initialization
def setup(bot):
    bot.add_cog(TrackingCog(bot))