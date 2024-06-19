# main.py
"""Contains error handling and the help and about commands"""

from typing import Union

import discord
from discord.ext import commands
from discord.commands import slash_command

from content import main
from database import errors, guilds
from resources import exceptions, functions, logs, settings


class MainCog(commands.Cog):
    """Cog with events and help and about commands"""
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # Commands
    @slash_command(name='event-reductions')
    async def event_reductions(self, ctx: discord.ApplicationContext) -> None:
        """Shows currently active event reductions"""
        await main.command_event_reduction(self.bot, ctx)

    @slash_command(description='Main help command')
    @commands.guild_only()
    async def help(self, ctx: discord.ApplicationContext) -> None:
        """Main help command"""
        await main.command_help(self.bot, ctx)

    @slash_command(description='Some info and links about me')
    async def about(self, ctx: discord.ApplicationContext) -> None:
        """About command"""
        await main.command_about(self.bot, ctx)

    @commands.command(name='help', aliases=('h',))
    @commands.bot_has_permissions(send_messages=True, embed_links=True)
    async def prefix_help(self, ctx: Union[commands.Context, discord.Message]) -> None:
        """Main help command (prefix version)"""
        await main.command_help(self.bot, ctx)

     # Events
    @commands.Cog.listener()
    async def on_application_command_error(self, ctx: discord.ApplicationContext, error: Exception) -> None:
        """Runs when an error occurs and handles them accordingly.
        Interesting errors get written to the database for further review.
        """
        command_name = f'{ctx.command.full_parent_name} {ctx.command.name}'.strip()
        command_name = await functions.get_bot_slash_command(self.bot, command_name)
        async def send_error() -> None:
            """Sends error message as embed"""
            embed = discord.Embed(title='An error occured')
            embed.add_field(name='Command', value=f'{command_name}', inline=False)
            embed.add_field(name='Error', value=f'```py\n{error}\n```', inline=False)
            await ctx.respond(embed=embed, ephemeral=True)

        error = getattr(error, 'original', error)
        if isinstance(error, commands.NoPrivateMessage):
            if ctx.guild_id is None:
                await ctx.respond(
                    f'I\'m sorry, this command is not available in DMs.',
                    ephemeral=True
                )
            else:
                await ctx.respond(
                    f'I\'m sorry, this command is not available in this server.\n\n'
                    f'To allow this, the server admin needs to reinvite me with the necessary permissions.\n',
                    ephemeral=True
                )
        elif isinstance(error, (commands.MissingPermissions, commands.MissingRequiredArgument,
                                commands.TooManyArguments, commands.BadArgument)):
            await send_error()
        elif isinstance(error, commands.BotMissingPermissions):
            await ctx.respond(
                f'You can\'t use this command in this channel.\n'
                f'To enable this, I need the permission `View Channel` / '
                f'`Read Messages` in this channel.',
                ephemeral=True
            )
        elif isinstance(error, commands.CommandOnCooldown):
            await ctx.respond(
                f'Hold your horses, wait another {error.retry_after:.1f}s before using this again.',
                ephemeral=True
            )
        elif isinstance(error, exceptions.FirstTimeUserError):
            await ctx.respond(
                f'Yeehaw! **{ctx.author.display_name}**, looks like I don\'t know you yet.\n'
                f'Use {await functions.get_bot_slash_command(self.bot, "on")} to activate me first.',
                ephemeral=True
            )
        elif isinstance(error, commands.NotOwner):
            await ctx.respond(
                f'As you might have guessed, you are not allowed to use this command.',
                ephemeral=True
            )
            await errors.log_error(error, ctx)
        elif isinstance(error, discord.errors.Forbidden):
            return
        else:
            await errors.log_error(error, ctx)
            if settings.DEBUG_MODE or ctx.guild.id in settings.DEV_GUILDS: await send_error()

    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context, error: Exception) -> None:
        """Runs when an error occurs and handles them accordingly.
        Interesting errors get written to the database for further review.
        """
        async def send_error() -> None:
            """Sends error message as embed"""
            embed = discord.Embed(title='An error occured')
            embed.add_field(name='Command', value=f'`{ctx.command.qualified_name}`', inline=False)
            embed.add_field(name='Error', value=f'```py\n{error}\n```', inline=False)
            await ctx.reply(embed=embed)

        error = getattr(error, 'original', error)
        if isinstance(error, (commands.CommandNotFound, commands.NotOwner)):
            return
        elif isinstance(error, commands.CommandOnCooldown):
            await ctx.reply(
                f'**{ctx.author.display_name}**, you can only use this command every '
                f'{int(error.cooldown.per)} seconds.\n'
                f'You have to wait another **{error.retry_after:.1f}s**.'
            )
        elif isinstance(error, commands.DisabledCommand):
            await ctx.reply(f'Command `{ctx.command.qualified_name}` is temporarily disabled.')
        elif isinstance(error, (commands.MissingPermissions, commands.MissingRequiredArgument,
                                commands.TooManyArguments, commands.BadArgument)):
            await send_error()
        elif isinstance(error, commands.BotMissingPermissions):
            if 'send_messages' in error.missing_permissions:
                return
            if 'embed_links' in error.missing_perms:
                await ctx.reply(error)
            else:
                await send_error()
        elif isinstance(error, exceptions.FirstTimeUserError):
            await ctx.reply(
                f'**{ctx.author.display_name}**, looks like I don\'t know you yet.\n'
                f'Use {await functions.get_bot_slash_command(self.bot, "on")} to activate me first.',
            )
        elif isinstance(error, (commands.UnexpectedQuoteError, commands.InvalidEndOfQuotedStringError,
                                commands.ExpectedClosingQuoteError)):
            await ctx.reply(
                f'**{ctx.author.display_name}**, whatever you just entered contained invalid characters I can\'t process.\n'
                f'Please try that again.'
            )
            await errors.log_error(error, ctx)
        elif isinstance(error, commands.CheckFailure):
            await ctx.respond(
                await ctx.respond('As you might have guessed, you are not allowed to use this command.',
                ephemeral=True)
            )
        elif isinstance(error, discord.errors.Forbidden):
            return
        else:
            await errors.log_error(error, ctx)
            if settings.DEBUG_MODE or ctx.guild.id in settings.DEV_GUILDS: await send_error()

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        """Runs when a message is sent in a channel."""
        if message.author.bot: return
        if (
            self.bot.user.mentioned_in(message)
            and (message.content.lower().replace('<@!','').replace('<@','').replace('>','')
                 .replace(str(self.bot.user.id),'')) == ''
        ):
            await self.prefix_help(message)

    # Events
    @commands.Cog.listener()
    async def on_ready(self) -> None:
        """Fires when bot has finished starting"""
        startup_info = f'{self.bot.user.name} has connected to Discord!'
        print(startup_info)
        logs.logger.info(startup_info)
        
    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild) -> None:
        """Fires when bot joins a guild. Sends a welcome message to the system channel."""
        try:
            guild_settings: guilds.Guild = await guilds.get_guild(guild.id)
            welcome_message = (
                f'Yeehaw! **{guild.name}**! I\'m here to help you with your IDLE FARMs!\n'
                f'Some of my commands have prefix versions. My current prefix for this server is '
                f'`{guild_settings.prefix}`. You can change this in '
                f'{await functions.get_bot_slash_command(self.bot, "settings server")}.\n\n'
                f'Note that I\'m off by default. Players that want to use me, need to use '
                f'{await functions.get_bot_slash_command(self.bot, "on")} to activate me.\n'
            )
            await guild.system_channel.send(welcome_message)
        except:
            return


# Initialization
def setup(bot):
    bot.add_cog(MainCog(bot))