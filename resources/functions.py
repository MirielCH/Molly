# functions.py

import asyncio
from datetime import timedelta
import re
from typing import Any, Coroutine, List, Optional, Union

import discord
from discord.ext import commands
from discord import utils

from database import cooldowns, errors, reminders, upgrades, users
from resources import emojis, exceptions, functions, regex, settings, strings, views


# --- Get discord data ---
async def get_interaction(message: discord.Message) -> discord.Interaction:
    """Returns the interaction object if the message was triggered by a slash command. Returns None if no user was found."""
    if message.reference is not None:
        if message.reference.cached_message is not None:
            message = message.reference.cached_message
        else:
            message = await message.channel.fetch_message(message.reference.message_id)
    return message.interaction


async def get_interaction_user(message: discord.Message) -> discord.User:
    """Returns the user object if the message was triggered by a slash command. Returns None if no user was found."""
    interaction = await get_interaction(message)
    return interaction.user if interaction is not None else None


async def get_discord_user(bot: discord.Bot, user_id: int) -> discord.User:
    """Checks the user cache for a user and makes an additional API call if not found. Returns None if user not found."""
    await bot.wait_until_ready()
    user = bot.get_user(user_id)
    if user is None:
        try:
            user = await bot.fetch_user(user_id)
        except discord.NotFound:
            pass
    return user


async def get_discord_channel(bot: discord.Bot, channel_id: int) -> discord.User:
    """Checks the channel cache for a channel and makes an additional API call if not found. Returns None if channel not found."""
    if channel_id is None: return None
    await bot.wait_until_ready()
    channel = bot.get_channel(channel_id)
    if channel is None:
        try:
            channel = await bot.fetch_channel(channel_id)
        except discord.NotFound:
            pass
        except discord.Forbidden:
            raise
    return channel


# --- Reactions
async def add_logo_reaction(message: discord.Message) -> None:
    """Adds a Molly reaction if not already added"""
    reaction_exists = False
    for reaction in message.reactions:
        if reaction.emoji == emojis.LOGO:
            reaction_exists = True
            break
    if not reaction_exists: await message.add_reaction(emojis.LOGO)
        

async def add_reminder_reaction(message: discord.Message, reminder: reminders.Reminder,  user_settings: users.User) -> None:
    """Adds a Molly reaction if the reminder was created, otherwise add a warning and send the error if debug mode is on"""
    if reminder.record_exists and user_settings.reactions_enabled:
        await add_logo_reaction(message)
    elif not reminder.record_exists:
        if settings.DEBUG_MODE or message.guild.id in settings.DEV_GUILDS:
            await message.add_reaction(emojis.WARNING)
            await message.channel.send(strings.MSG_ERROR)


async def add_warning_reaction(message: discord.Message) -> None:
    """Adds a warning reaction if debug mode is on or the guild is a dev guild"""
    if settings.DEBUG_MODE or message.guild.id in settings.DEV_GUILDS:
        await message.add_reaction(emojis.WARNING)


# --- Regex ---
async def get_match_from_patterns(patterns: List[str], string: str) -> re.Match:
    """Searches a string for a regex patterns out of a list of patterns and returns the first match.
    Returns None if no match is found.
    """
    for pattern in patterns:
        match = re.search(pattern, string, re.IGNORECASE)
        if match: break
    return match


# --- Time calculations ---
async def get_guild_member_by_name(guild: discord.Guild, user_name: str,
                                   bot_users_only: Optional[bool] = True) -> List[discord.Member]:
    """Returns all guild members found by the given name"""
    members = []
    for member in guild.members:
        if await encode_text(member.name) == await encode_text(user_name) and not member.bot:
            if bot_users_only:
                try:
                    await users.get_user(member.id)
                except exceptions.FirstTimeUserError:
                    continue
            members.append(member)
    return members


async def calculate_time_left_from_cooldown(message: discord.Message, user_settings: users.User, activity: str) -> timedelta:
    """Returns the time left for a reminder based on a cooldown."""
    slash_command = True if message.interaction is not None else False
    cooldown: cooldowns.Cooldown = await cooldowns.get_cooldown(activity)
    bot_answer_time = message.created_at.replace(microsecond=0)
    current_time = utils.utcnow().replace(microsecond=0)
    time_elapsed = current_time - bot_answer_time
    actual_cooldown = cooldown.actual_cooldown_slash() if slash_command else cooldown.actual_cooldown_mention()
    if cooldown.donor_affected:
        time_left_seconds = (actual_cooldown
                             * settings.DONOR_TIERS_MULTIPLIERS[user_settings.donor_tier]
                             - time_elapsed.total_seconds())
    else:
        time_left_seconds = actual_cooldown - time_elapsed.total_seconds()
    return timedelta(seconds=time_left_seconds)


async def calculate_time_left_from_timestring(message: discord.Message, timestring: str) -> timedelta:
    """Returns the time left for a reminder based on a timestring."""
    time_left = await parse_timestring_to_timedelta(timestring.lower())
    bot_answer_time = message.created_at.replace(microsecond=0)
    current_time = utils.utcnow().replace(microsecond=0)
    time_elapsed = current_time - bot_answer_time
    return time_left - time_elapsed


async def check_timestring(string: str) -> str:
    """Checks if a string is a valid timestring. Returns itself it valid.

    Raises
    ------
    ErrorInvalidTime if timestring is not a valid timestring.
    """
    last_time_code = None
    last_char_was_number = False
    timestring = ''
    current_number = ''
    pos = 0
    while not pos == len(string):
        slice = string[pos:pos+1]
        pos = pos+1
        allowedcharacters_numbers = set('1234567890')
        allowedcharacters_timecode = set('wdhms')
        if set(slice).issubset(allowedcharacters_numbers):
            timestring = f'{timestring}{slice}'
            current_number = f'{current_number}{slice}'
            last_char_was_number = True
        elif set(slice).issubset(allowedcharacters_timecode) and last_char_was_number:
            if slice == 'w':
                if last_time_code is None:
                    timestring = f'{timestring}w'
                    try:
                        current_number_numeric = int(current_number)
                    except:
                        raise exceptions.InvalidTimestringError('Invalid timestring.')
                    last_time_code = 'weeks'
                    last_char_was_number = False
                    current_number = ''
                else:
                    raise exceptions.InvalidTimestringError('Invalid timestring.')
            elif slice == 'd':
                if last_time_code in ('weeks',None):
                    timestring = f'{timestring}d'
                    try:
                        current_number_numeric = int(current_number)
                    except:
                        raise exceptions.InvalidTimestringError('Invalid timestring.')
                    last_time_code = 'days'
                    last_char_was_number = False
                    current_number = ''
                else:
                    raise exceptions.InvalidTimestringError('Invalid timestring.')
            elif slice == 'h':
                if last_time_code in ('weeks','days',None):
                    timestring = f'{timestring}h'
                    try:
                        current_number_numeric = int(current_number)
                    except:
                        raise exceptions.InvalidTimestringError('Invalid timestring.')
                    last_time_code = 'hours'
                    last_char_was_number = False
                    current_number = ''
                else:
                    raise exceptions.InvalidTimestringError('Invalid timestring.')
            elif slice == 'm':
                if last_time_code in ('weeks','days','hours',None):
                    timestring = f'{timestring}m'
                    try:
                        current_number_numeric = int(current_number)
                    except:
                        raise exceptions.InvalidTimestringError('Invalid timestring.')
                    last_time_code = 'minutes'
                    last_char_was_number = False
                    current_number = ''
                else:
                    raise exceptions.InvalidTimestringError('Invalid timestring.')
            elif slice == 's':
                if last_time_code in ('weeks','days','hours','minutes',None):
                    timestring = f'{timestring}s'
                    try:
                        current_number_numeric = int(current_number)
                    except:
                        raise exceptions.InvalidTimestringError('Invalid timestring.')
                    last_time_code = 'seconds'
                    last_char_was_number = False
                    current_number = ''
                else:
                    raise exceptions.InvalidTimestringError('Invalid timestring.')
            else:
                raise exceptions.InvalidTimestringError('Invalid timestring.')
        else:
            raise exceptions.InvalidTimestringError('Invalid timestring.')
    if last_char_was_number:
        raise exceptions.InvalidTimestringError('Invalid timestring.')

    return timestring


async def parse_timestring_to_timedelta(timestring: str) -> timedelta:
    """Parses a time string and returns the time as timedelta."""
    time_left_seconds = 0

    if '-' in timestring: return timedelta(days=-1)
    if 'ms' in timestring: return timedelta(seconds=1)
    if 'y' in timestring:
        years_start = 0
        years_end = timestring.find('y')
        years = timestring[years_start:years_end]
        timestring = timestring[years_end+1:].strip()
        try:
            time_left_seconds = time_left_seconds + (int(years) * 52 * 604800)
        except:
            await errors.log_error(
                f'Error parsing timestring \'{timestring}\', couldn\'t convert \'{years}\' to an integer'
            )
    if 'w' in timestring:
        weeks_start = 0
        weeks_end = timestring.find('w')
        weeks = timestring[weeks_start:weeks_end]
        timestring = timestring[weeks_end+1:].strip()
        try:
            time_left_seconds = time_left_seconds + (int(weeks) * 604800)
        except:
            await errors.log_error(
                f'Error parsing timestring \'{timestring}\', couldn\'t convert \'{weeks}\' to an integer'
            )
    if 'd' in timestring:
        days_start = 0
        days_end = timestring.find('d')
        days = timestring[days_start:days_end]
        timestring = timestring[days_end+1:].strip()
        try:
            time_left_seconds = time_left_seconds + (int(days) * 86400)
        except:
            await errors.log_error(
                f'Error parsing timestring \'{timestring}\', couldn\'t convert \'{days}\' to an integer'
            )
    if 'h' in timestring:
        hours_start = 0
        hours_end = timestring.find('h')
        hours = timestring[hours_start:hours_end]
        timestring = timestring[hours_end+1:].strip()
        try:
            time_left_seconds = time_left_seconds + (int(hours) * 3600)
        except:
            await errors.log_error(
                f'Error parsing timestring \'{timestring}\', couldn\'t convert \'{hours}\' to an integer'
            )
    if 'm' in timestring:
        minutes_start = 0
        minutes_end = timestring.find('m')
        minutes = timestring[minutes_start:minutes_end]
        timestring = timestring[minutes_end+1:].strip()
        try:
            time_left_seconds = time_left_seconds + (int(minutes) * 60)
        except:
            await errors.log_error(
                f'Error parsing timestring \'{timestring}\', couldn\'t convert \'{minutes}\' to an integer'
            )
    if 's' in timestring:
        seconds_start = 0
        seconds_end = timestring.find('s')
        seconds = timestring[seconds_start:seconds_end]
        decimal_point_location = seconds.find('.')
        if decimal_point_location > -1:
            seconds = seconds[:decimal_point_location]
        timestring = timestring[seconds_end+1:].strip()
        try:
            time_left_seconds = time_left_seconds + int(seconds)
        except:
            await errors.log_error(
                f'Error parsing timestring \'{timestring}\', couldn\'t convert \'{seconds}\' to an integer'
            )

    if time_left_seconds > 999_999_999:
        raise OverflowError('Timestring out of valid range. Stop hacking.')

    return timedelta(seconds=time_left_seconds)


async def parse_timedelta_to_timestring(time_left: timedelta) -> str:
    """Creates a time string from a timedelta."""
    years = time_left.total_seconds() // 31_536_000
    years = int(years)
    weeks = (time_left.total_seconds() % 31_536_000) // 604_800
    weeks = int(weeks)
    days = (time_left.total_seconds() % 604_800) // 86_400
    days = int(days)
    hours = (time_left.total_seconds() % 86_400) // 3_600
    hours = int(hours)
    minutes = (time_left.total_seconds() % 3_600) // 60
    minutes = int(minutes)
    seconds = time_left.total_seconds() % 60
    seconds = int(seconds)

    timestring = ''
    if not years == 0:
        timestring = f'{timestring}{years}y '
    if not weeks == 0:
        timestring = f'{timestring}{weeks}w '
    if not days == 0:
        timestring = f'{timestring}{days}d '
    if not hours == 0:
        timestring = f'{timestring}{hours}h '
    if not minutes == 0:
        timestring = f'{timestring}{minutes}m '
    if not seconds == 0:
        timestring = f'{timestring}{seconds}s '
    if timestring == '':
        timestring = '0m 0s'

    return timestring.strip()


# --- Message processing ---
async def encode_text(text: str) -> str:
    """Encodes all unicode characters in a text in a way that is consistent on both Windows and Linux"""
    text = (
        text
        .encode('unicode-escape',errors='ignore')
        .decode('ASCII')
        .replace('\\','')
        .strip('*')
    )

    return text


def encode_text_non_async(text: str) -> str:
    """Encodes all unicode characters in a text in a way that is consistent on both Windows and Linux (non async)"""
    text = (
        text
        .encode('unicode-escape',errors='ignore')
        .decode('ASCII')
        .replace('\\','')
        .strip('*')
    )

    return text


async def encode_message(bot_message: discord.Message) -> str:
    """Encodes a message to a version that converts all potentionally problematic unicode characters (async)"""
    if not bot_message.embeds:
        message = await encode_text(bot_message.content)
    else:
        embed: discord.Embed = bot_message.embeds[0]
        message_author = message_description = message_fields = message_title = ''
        if embed.author: message_author = await encode_text(str(embed.author))
        if embed.description: message_description = await encode_text(str(embed.description))
        if embed.title: message_title = str(embed.title)
        if embed.fields: message_fields = str(embed.fields)
        message = f'{message_author}{message_description}{message_fields}{message_title}'

    return message


def encode_message_non_async(bot_message: discord.Message) -> str:
    """Encodes a message to a version that converts all potentionally problematic unicode characters (non async)"""
    if not bot_message.embeds:
        message = encode_text_non_async(bot_message.content)
    else:
        embed: discord.Embed = bot_message.embeds[0]
        message_author = message_description = message_fields = message_title = ''
        if embed.author: message_author = encode_text_non_async(str(embed.author))
        if embed.description: message_description = encode_text_non_async(str(embed.description))
        if embed.title: message_title = str(embed.title)
        if embed.fields: message_fields = str(embed.fields)
        message = f'{message_author}{message_description}{message_fields}{message_title}'

    return message


async def encode_message_with_fields(bot_message: discord.Message) -> str:
    """Encodes a message to a version that converts all potentionally problematic unicode characters
    (async, fields encoded)"""
    if not bot_message.embeds:
        message = await encode_text(bot_message.content)
    else:
        embed: discord.Embed = bot_message.embeds[0]
        message_author = message_description = message_fields = message_title = ''
        if embed.author: message_author = await encode_text(str(embed.author))
        if embed.description: message_description = await encode_text(str(embed.description))
        if embed.title: message_title = str(embed.title)
        if embed.fields: message_fields = await encode_text(str(embed.fields))
        message = f'{message_author}{message_description}{message_fields}{message_title}'

    return message


def encode_message_with_fields_non_async(bot_message: discord.Message) -> str:
    """Encodes a message to a version that converts all potentionally problematic unicode characters
    (non async, fields encoded)"""
    if not bot_message.embeds:
        message = encode_text_non_async(bot_message.content)
    else:
        embed: discord.Embed = bot_message.embeds[0]
        message_author = message_description = message_fields = message_title = ''
        if embed.author: message_author = encode_text_non_async(str(embed.author))
        if embed.description: message_description = encode_text_non_async(str(embed.description))
        if embed.title: message_title = str(embed.title)
        if embed.fields: message_fields = encode_text_non_async(str(embed.fields))
        message = f'{message_author}{message_description}{message_fields}{message_title}'

    return message


# Miscellaneous
async def call_ready_command(bot: commands.Bot, message: discord.Message, user: discord.User) -> None:
    """Calls the ready command as a reply to the current message"""
    command = bot.get_application_command(name='ready')
    if command is not None: await command.callback(command.cog, message, user=user)


async def get_game_command(user_settings: users.User, command_name: str) -> str:
    """Gets a game command. Slash or text, depending on user setting."""
    if user_settings.reminders_slash_enabled:
        return strings.SLASH_COMMANDS.get(command_name, None)
    else:
        return command_name


async def get_bot_slash_command(bot: discord.Bot, command_name: str) -> str:
    """Gets a slash command from the bot. If found, returns the slash mention. If not found, just returns /command.
    Note that slash mentions only work with GLOBAL commands."""
    main_command, *sub_commands = command_name.lower().split(' ')
    for command in bot.application_commands:
        if command.name == main_command:
            return f'</{command_name}:{command.id}>'
    return f'`/{command_name}`'


def await_coroutine(coro):
    """Function to call a coroutine outside of an async function"""
    while True:
        try:
            coro.send(None)
        except StopIteration as error:
            return error.value


async def edit_interaction(interaction: Union[discord.Interaction, discord.WebhookMessage], **kwargs) -> None:
    """Edits a reponse. The response can either be an interaction OR a WebhookMessage"""
    content = kwargs.get('content', utils.MISSING)
    embed = kwargs.get('embed', utils.MISSING)
    embeds = kwargs.get('embeds', utils.MISSING)
    view = kwargs.get('view', utils.MISSING)
    file = kwargs.get('file', utils.MISSING)
    if isinstance(interaction, discord.WebhookMessage):
        await interaction.edit(content=content, embed=embed, embeds=embeds, view=view)
    else:
        await interaction.edit_original_response(content=content, file=file, embed=embed, embeds=embeds, view=view)


async def bool_to_text(boolean: bool) -> str:
        return f'{emojis.ENABLED}`Enabled`' if boolean else f'{emojis.DISABLED}`Disabled`'


async def reply_or_respond(ctx: Union[discord.ApplicationContext, commands.Context], answer: str,
                           ephemeral: Optional[bool] = False) -> Union[discord.Message, discord.Integration]:
    """Sends a reply or reponse, depending on the context type"""
    if isinstance(ctx, commands.Context):
        return await ctx.reply(answer)
    else:
        return await ctx.respond(answer, ephemeral=ephemeral)


async def get_inventory_item(inventory: str, emoji_name: str) -> int:
    """Extracts the amount of a material from an inventory
    Because the material is only listed with its emoji, the exact and full emoji name needs to be given."""
    material_match = re.search(fr'`\s*([\d,.km]+?)`\*\* <:{emoji_name}:\d+>', inventory, re.IGNORECASE)
    if not material_match: return 0
    amount_patterns = [
        r'(\d+[\.,]\d+[km]?)',
        r'(\d+)',
    ]
    amount_match = await functions.get_match_from_patterns(amount_patterns, material_match.group(1))
    amount = amount_match.group(1)
    if amount.lower().endswith('k'):
        return int(float(amount.lower().rstrip('k')) * 1_000)
    elif amount.lower().endswith('m'):
        return int(float(amount.lower().rstrip('m')) * 1_000_000)
    else:
        amount = amount.replace(',','').replace('.','')
        if amount.isnumeric():
            return int(amount)
        else:
            raise ValueError(f'Inventory amount "{amount}" can\'t be parsed.')        


async def get_result_from_tasks(ctx: discord.ApplicationContext, tasks: List[asyncio.Task]) -> Any:
    """Returns the first result from several running asyncio tasks."""
    try:
        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
    except asyncio.CancelledError:
        return
    for task in pending:
        if not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
    try:
        result = list(done)[0].result()
    except asyncio.CancelledError:
        pass
    except asyncio.TimeoutError as error:
        raise
    except Exception as error:
        await errors.log_error(error, ctx)
        raise
    return result


# Wait for input
async def wait_for_bot_or_abort(ctx: discord.ApplicationContext, bot_message_task: Coroutine,
                                content: str) -> Union[discord.Message, None]:
    """Sends a message with an abort button that tells the user to input a command.
    This function then waits for both view input and bot_message_task.
    If the bot message task finishes first, the bot message is returned, otherwise return value is None.

    The abort button is removed after this function finishes.
    Make sure that the view timeout is longer than the bot message task timeout to get proper errors.

    Arguments
    ---------
    ctx: Context.
    bot_message_task: The task with the coroutine that waits for the EPIC RPG message.
    content: The content of the message that tells the user what to enter.

    Returns
    -------
    Bot message if message task finished first.
    None if the interaction was aborted or the view timed out first.

    Raises
    ------
    asyncio.TimeoutError if the bot message task timed out before the view timed out.
    This error is also logged to the database.
    """
    view = views.AbortView(ctx)
    interaction = await ctx.respond(content, view=view)
    view.interaction = interaction
    view_task = asyncio.ensure_future(view.wait())
    done, pending = await asyncio.wait([bot_message_task, view_task], return_when=asyncio.FIRST_COMPLETED)
    for task in pending:
        if not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
    if view.value in ('abort','timeout'):
        try:
            await edit_interaction(interaction, content=strings.MSG_ABORTED, view=None)
        except discord.errors.NotFound:
            pass
    elif view.value is None:
        view.stop()
        asyncio.ensure_future(edit_interaction(interaction, view=None))
    bot_message = None
    if bot_message_task.done():
        try:
            bot_message = bot_message_task.result()
        except asyncio.CancelledError:
            pass
        except asyncio.TimeoutError as error:
            raise
        except Exception as error:
            await errors.log_error(error, ctx)
            raise

    return bot_message


async def wait_for_inventory_message(bot: commands.Bot, ctx: discord.ApplicationContext) -> discord.Message:
    """Waits for and returns the message with the inventory embed from Tree"""
    def game_check(message_before: discord.Message, message_after: Optional[discord.Message] = None):
        correct_message = False
        message = message_after if message_after is not None else message_before
        if message.embeds:
            embed = message.embeds[0]
            if embed.author:
                embed_author = encode_text_non_async(str(embed.author.name))
                icon_url = embed.author.icon_url
                try:
                    user_id_match = re.search(regex.USER_ID_FROM_ICON_URL, icon_url)
                    if user_id_match:
                        user_id = int(user_id_match.group(1))
                        search_strings = [
                            f'\'s inventory', #All languages
                        ]
                        if (any(search_string in embed_author for search_string in search_strings)
                            and user_id == ctx.author.id):
                            correct_message = True
                    else:
                        ctx_author = encode_text_non_async(ctx.author.name)
                        search_strings = [
                            f'{ctx_author}\'s inventory', ##All languages
                        ]
                        if any(search_string in embed_author for search_string in search_strings):
                            correct_message = True
                except:
                    pass

        return ((message.author.id in (settings.GAME_ID, settings.TESTY_ID)) and (message.channel == ctx.channel)
                and correct_message)

    message_task = asyncio.ensure_future(bot.wait_for('message', check=game_check,
                                                      timeout = settings.ABORT_TIMEOUT))
    message_edit_task = asyncio.ensure_future(bot.wait_for('message_edit', check=game_check,
                                                           timeout = settings.ABORT_TIMEOUT))
    result = await get_result_from_tasks(ctx, [message_task, message_edit_task])
    return result[1] if isinstance(result, tuple) else result


async def get_energy_regen_time(user_settings: users.User) -> timedelta:
    """Returns the time it takes to generate 1 energy"""
    try:
        energy_upgrade: upgrades.Upgrade = await upgrades.get_upgrade(user_settings.user_id, 'energy regeneration')
        multiplier_upgrade = strings.ENERGY_UPGRADE_LEVEL_MULTIPLIERS[energy_upgrade.level]
    except exceptions.NoDataFoundError:
        multiplier_upgrade = 1
    multiplier_donor = list(strings.DONOR_TIER_ENERGY_MULTIPLIERS.values())[user_settings.donor_tier]
    energy_regen = 5 / (multiplier_donor * multiplier_upgrade)
    return timedelta(minutes=energy_regen)


async def get_current_energy_amount(user_settings: users.User, energy_regen_time: Optional[timedelta] = None) -> int:
    """Returns the energy amount the user currently has based on energy_max and energy_full_time
    The amount is NOT rounded.
    """
    current_time = utils.utcnow()
    if user_settings.energy_full_time is None:
        raise exceptions.EnergyFullTimeNoneError
    if user_settings.energy_full_time <= current_time:
        raise exceptions.EnergyFullTimeOutdatedError
    if energy_regen_time is None:
        energy_regen_time = await get_energy_regen_time(user_settings)
    energy_until_max = (user_settings.energy_full_time - current_time).total_seconds() / energy_regen_time.total_seconds()
    return int(user_settings.energy_max - energy_until_max)


async def change_user_energy(user_settings: users.User, energy_amount: int) -> None:
    """Recalculates and updates energy_full_time for a user object based on an energy amount. The time it takes
    to generate the provided energy amount is added to the current energy_full_time.
    The energy amount can be negative which will shorten energy_full_time accordingly.

    If an energy reminder is active, this also updates the reminder end time.
    """
    if user_settings.energy_full_time is None: return
    energy_regen_time = await get_energy_regen_time(user_settings)
    amount_negative = False
    energy_amount_original = energy_amount
    if energy_amount < 0:
        energy_amount *= -1
        amount_negative = True
    energy_current = await get_current_energy_amount(user_settings, energy_regen_time)
    current_time = utils.utcnow()
    if energy_amount_original > (user_settings.energy_max - energy_current):
        energy_full_time_new = current_time
    else:
        energy_amount_time = timedelta(seconds=energy_amount * energy_regen_time.total_seconds())
        if amount_negative:
            energy_full_time_new = user_settings.energy_full_time + energy_amount_time
        else:
            energy_full_time_new = user_settings.energy_full_time - energy_amount_time
    await user_settings.update(energy_full_time=energy_full_time_new)
    await recalculate_energy_reminder(user_settings, energy_regen_time)


async def recalculate_energy_reminder(user_settings: users.User, energy_regen_time: Optional[timedelta] = None) -> None:
    """Recalculates the end time of an energy reminder based on energy_max and energy_full_time in the user settings."""
    try:
        reminder: reminders.Reminder = await reminders.get_user_reminder(user_settings.user_id, 'energy')
        if energy_regen_time is None:
            energy_regen_time = await get_energy_regen_time(user_settings)
        energy_current = await get_current_energy_amount(user_settings, energy_regen_time)
        energy_amount_reminder = int(reminder.activity[7:])
        current_time = utils.utcnow()
        reminder_end_time_new = (
            current_time
            + timedelta(seconds=(energy_amount_reminder - energy_current) * energy_regen_time.total_seconds())
        )
        if reminder_end_time_new <= current_time: reminder_end_time_new = current_time + timedelta(seconds=1)
        await reminder.update(end_time=reminder_end_time_new)
    except exceptions.NoDataFoundError:
        return