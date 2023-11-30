# use.py

from datetime import timedelta
import re
from typing import Dict, Optional

import discord
from discord import utils

from cache import messages
from database import reminders, users
from resources import exceptions, functions, regex, strings


async def process_message(bot: discord.Bot, message: discord.Message, embed_data: Dict, user: Optional[discord.User],
                          user_settings: Optional[users.User]) -> bool:
    """Processes the message for all /use related actions.

    Returns
    -------
    - True if a logo reaction should be added to the message
    - False otherwise
    """
    return_values = []
    return_values.append(await call_context_helper_on_energy_item(message, embed_data, user, user_settings))
    return_values.append(await track_time_items(message, user))
    return any(return_values)


async def call_context_helper_on_energy_item(message: discord.Message, embed_data: Dict, user: Optional[discord.User],
                                              user_settings: Optional[users.User]) -> bool:
    """Call the context helper when using an energy item

    Returns
    -------
    - True if a logo reaction should be added to the message
    - False otherwise
    """
    add_reaction = False
    search_strings = [
        '**energy** was recovered!', #English
    ]

    if any(search_string in message.content.lower() for search_string in search_strings):
        if user is None:
            user_name_match = re.search(regex.NAME_FROM_MESSAGE_START, message.content)
            user_name = user_name_match.group(1)
            user_command_message = (
                await messages.find_message(message.channel.id, regex.COMMAND_USE_ENERGY_ITEM, user_name=user_name)
            )
            user = user_command_message.author
        if user_settings is None:
            try:
                user_settings: users.User = await users.get_user(user.id)
            except exceptions.FirstTimeUserError:
                return add_reaction
        if not user_settings.bot_enabled: return add_reaction
        if user_settings.helper_context_enabled:
            await message.reply(
                f"➜ {strings.SLASH_COMMANDS['claim']}\n"
                f"➜ {strings.SLASH_COMMANDS['raid']}\n"
                f"➜ {strings.SLASH_COMMANDS['worker hire']}"
            )
        energy_amount_match = re.search(r'>\s([0-9,]+)\s\*\*', message.content.lower())
        energy_amount = int(re.sub('\D','', energy_amount_match.group(1)))
        try:
            await functions.change_user_energy(user_settings, energy_amount)
            if user_settings.reactions_enabled: add_reaction = True
        except exceptions.EnergyFullTimeOutdatedError:
            await message.reply(strings.MSG_ENERGY_OUTDATED.format(user=user.display_name,
                                                                   cmd_profile=strings.SLASH_COMMANDS["profile"]))
        except exceptions.EnergyFullTimeNoneError:
            pass
    return add_reaction


async def track_time_items(message: discord.Message, user: discord.User) -> bool:
    """Tacks time speeders and compressors used

    Returns
    -------
    - True if a logo reaction should be added to the message
    - False otherwise
    """
    add_reaction = False
    search_strings = [
        'timespeeder',
        'timecompressor',
    ]
    if any(search_string in message.content.lower() for search_string in search_strings) and '🕓' in message.content.lower():
        if user is None:
            user_name_match = re.search(regex.NAME_FROM_MESSAGE_START, message.content.lower())
            user_name = user_name_match.group(1)
            user_command_message = (
                await messages.find_message(message.channel.id, regex.COMMAND_USE_TIME_ITEM, user_name=user_name)
            )
            user = user_command_message.author
        try:
            user_settings: users.User = await users.get_user(user.id)
        except exceptions.FirstTimeUserError:
            return add_reaction
        if not user_settings.bot_enabled: return add_reaction
        timestring_match = re.search(r'🕓 \*\*(.+?)\*\*', message.content.lower())
        item_time_left = await functions.parse_timestring_to_timedelta(timestring_match.group(1))
        kwargs = {}
        if 'timespeeder' in message.content.lower():
            items_used = item_time_left.total_seconds() // 7200
            kwargs['time_speeders_used'] = user_settings.time_speeders_used + items_used
        else:
            items_used = item_time_left.total_seconds() // 14400
            kwargs['time_compressors_used'] = user_settings.time_compressors_used + items_used
        await user_settings.update(**kwargs)
        try:
            claim_reminder: reminders.Reminder = await reminders.get_user_reminder(user.id, 'claim')
        except exceptions.NoDataFoundError:
            claim_reminder = []
        if claim_reminder and not claim_reminder.triggered:
            current_time = utils.utcnow()
            time_left = claim_reminder.end_time - current_time
            if time_left <= item_time_left:
                time_left = timedelta(seconds=1)
            else:
                time_left = time_left - item_time_left
            await claim_reminder.update(end_time=current_time + time_left)
            if user_settings.reactions_enabled: add_reaction = True
    return add_reaction