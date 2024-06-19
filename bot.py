# bot.py

from datetime import datetime
import sys
import traceback

import discord
from discord import utils
from discord.ext import commands

from database import errors, guilds
from database import settings as settings_db
from resources import functions, settings


startup_time = datetime.isoformat(utils.utcnow().replace(microsecond=0), sep=' ')
functions.await_coroutine(settings_db.update_setting('startup_time', startup_time))

intents = discord.Intents.none()
intents.guilds = True   # for on_guild_join() and all guild objects
intents.messages = True   # for command detection
intents.members = True  # To be able to look up user info
intents.message_content = True # for command detection

allowed_mentions = discord.AllowedMentions(everyone=False, roles=False, replied_user=False)

bot_activity: discord.Activity = discord.Activity(type=discord.ActivityType.playing, name='in your farm')
if settings.DEBUG_MODE:
    bot = commands.AutoShardedBot(command_prefix=guilds.get_all_prefixes, help_command=None,
                                  case_insensitive=True, intents=intents, owner_id=settings.OWNER_ID,
                                  allowed_mentions=allowed_mentions, debug_guilds=settings.DEV_GUILDS, activity=bot_activity)
else:
    bot = commands.AutoShardedBot(command_prefix=guilds.get_all_prefixes, help_command=None,
                                  case_insensitive=True, intents=intents, allowed_mentions=allowed_mentions,
                                  owner_id=settings.OWNER_ID, activiy=bot_activity)


@bot.event
async def on_error(event: str, *args, **kwargs) -> None:
    """Runs when an error outside a command appears.
    All errors get written to the database for further review.
    """
    if event == 'on_message':
        message, = args
        if message.channel.type.name == 'private': return
        embed = discord.Embed(title='An error occured')
        error = sys.exc_info()
        if isinstance(error[1], discord.errors.Forbidden): return
        traceback_str = "".join(traceback.format_tb(error[2]))
        traceback_message = f'{error[1]}\n{traceback_str}'
        embed.add_field(name='Event', value=f'`{event}`', inline=False)
        embed.add_field(name='Error', value=f'```py\n{traceback_message[:1015]}```', inline=False)
        await errors.log_error(f'- Event: {event}\n- Error: {error[1]}\n- Traceback:\n{traceback_str}', message)
        if settings.DEBUG_MODE:
            await message.channel.send(embed=embed)
            await functions.add_warning_reaction(message)
    else:
        try:
            message, _ = args
        except:
            return
        embed = discord.Embed(title='An error occured')
        error = sys.exc_info()
        if isinstance(error[1], discord.errors.Forbidden): return
        traceback_str = "".join(traceback.format_tb(error[2]))
        traceback_message = f'{error[1]}\n{traceback_str}'
        embed.add_field(name='Error', value=f'```py\n{traceback_message[:1015]}```', inline=False)
        await errors.log_error(f'- Event: {event}\n- Error: {error[1]}\n- Traceback:\n{traceback_str}', message)
        if settings.DEBUG_MODE:
            await message.channel.send(embed=embed)
            await functions.add_warning_reaction(message)
        if event == 'on_reaction_add':
            reaction, user = args
            return
        elif event == 'on_command_error':
            ctx, error = args
            raise
        else:
            return

EXTENSIONS = [
    'cogs.cache',
    'cogs.clan',
    'cogs.detection',
    'cogs.dev',
    'cogs.main',
    'cogs.misc',
    'cogs.reminders',
    'cogs.settings',
    'cogs.tracking',
    'cogs.tasks',
    'cogs.workers',
]

if __name__ == '__main__':
    for extension in EXTENSIONS:
        bot.load_extension(extension)


bot.run(settings.TOKEN)