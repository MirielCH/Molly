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

    @commands.command(name='reminder', aliases=('rm','remind','add','add-reminder','rm-add','reminders-add','reminder-add'))
    @commands.bot_has_permissions(send_messages=True)
    async def prefix_reminders_custom(self, ctx: commands.Context, *args: str) -> None:
        """Adds a custom reminder (prefix version)"""
        prefix = ctx.prefix
        syntax_add = (
            f'The syntax is `{prefix}{ctx.invoked_with} [time] [text]`\n'
            f'Supported time codes: `w`, `d`, `h`, `m`, `s`\n\n'
            f'Example: `{prefix}rm 1h30m Coffee time!`'
        )
        if not args:
            await ctx.reply(
                f'This command lets you add a custom reminder.\n'
                f'{syntax_add}\n\n'
                f'You can delete custom reminders in {await functions.get_bot_slash_command(self.bot, "list")}.\n'
            )
            return
        args = list(args)
        timestring = args[0].lower()
        args.pop(0)
        reminder_text = ' '.join(args) if args else 'you wanted to get reminded for idk, something?'
        await reminders_custom.command_custom_reminder(ctx, timestring, reminder_text)

    @commands.command(name='list', aliases=('cd','cooldown','cooldowns','lastclaim','lc','claim','daily','teamraid',
                                            'rd','ready',))
    @commands.bot_has_permissions(send_messages=True, embed_links=True)
    async def prefix_reminders_list(self, ctx: commands.Context, *args: str) -> None:
        """Lists all active reminders (prefix version)"""
        for mentioned_user in ctx.message.mentions.copy():
            if mentioned_user == self.bot.user:
                ctx.message.mentions.remove(mentioned_user)
                break
        if ctx.message.mentions:
            user = ctx.message.mentions[0]
        if not args:
            user = ctx.author
        else:
            arg = args[0].lower().replace('<@!','').replace('<@','').replace('>','')
            if not arg.isnumeric():
                await ctx.reply('Invalid user.')
                return
            user_id = int(arg)
            user = await functions.get_discord_user(self.bot, user_id)
            if user is None:
                await ctx.reply('This user doesn\'t exist.')
                return
        if user.bot:
            await ctx.reply('Imagine trying to check the reminders of a bot.')
            return
        await reminders_lists.command_list(self.bot, ctx, user)


# Initialization
def setup(bot):
    bot.add_cog(RemindersCog(bot))