# daily.py

from datetime import timedelta
import random
import re
from typing import Dict, Optional

import discord
from discord import utils

from cache import messages
from database import reminders, users
from resources import exceptions, functions, regex


async def process_message(bot: discord.Bot, message: discord.Message, embed_data: Dict, user: Optional[discord.User],
                          user_settings: Optional[users.User]) -> bool:
    """Processes the message for all daily related actions.

    Returns
    -------
    - True if a logo reaction should be added to the message
    - False otherwise
    """
    return_values = []
    return_values.append(await create_reminder(message, embed_data, user, user_settings))
    return any(return_values)


async def create_reminder(message: discord.Message, embed_data: Dict, user: Optional[discord.User],
                          user_settings: Optional[users.User]) -> bool:
    """Create a reminder on /daily

    Returns
    -------
    - True if a logo reaction should be added to the message
    - False otherwise
    """
    add_reaction = False
    search_strings = [
        '— daily reward', #All languages
    ]
    if any(search_string in embed_data['author']['name'].lower() for search_string in search_strings):
        if user is None:
            if embed_data['embed_user'] is not None:
                user = embed_data['embed_user']
                user_settings = embed_data['embed_user_settings']
            else:
                user_name_match = re.search(regex.USERNAME_FROM_EMBED_AUTHOR, embed_data['author']['name'])
                user_name = user_name_match.group(1)
                user_command_message = (
                    await messages.find_message(message.channel.id, regex.COMMAND_DAILY, user_name=user_name)
                )
                user = user_command_message.author
        if user_settings is None:
            try:
                user_settings: users.User = await users.get_user(user.id)
            except exceptions.FirstTimeUserError:
                return add_reaction
        if not user_settings.bot_enabled or not user_settings.reminder_daily.enabled: return add_reaction
        user_command = await functions.get_game_command(user_settings, 'daily')
        current_time = utils.utcnow()
        midnight_today = utils.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        end_time = midnight_today + timedelta(days=1, seconds=random.randint(60, 300))
        time_left = end_time - current_time
        if time_left < timedelta(0): return add_reaction
        reminder_message = (
            user_settings.reminder_daily.message
            .replace('{command}', user_command)
            .replace('{daily_reset_time}', utils.format_dt(midnight_today + timedelta(days=1), "R"))
        )
        reminder: reminders.Reminder = (
            await reminders.insert_user_reminder(user.id, 'daily', time_left,
                                            message.channel.id, reminder_message)
        )
        if user_settings.reactions_enabled and reminder.record_exists: add_reaction = True
    return add_reaction