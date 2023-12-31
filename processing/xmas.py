# xmas.py

from datetime import timedelta
import re
from typing import Dict, Optional

import discord

from cache import messages
from database import reminders, users
from resources import emojis, exceptions, functions, regex


async def process_message(bot: discord.Bot, message: discord.Message, embed_data: Dict, user: Optional[discord.User],
                          user_settings: Optional[users.User]) -> bool:
    """Processes the message for all christmas related actions.

    Returns
    -------
    - True if a logo reaction should be added to the message
    - False otherwise
    """
    return_values = []
    return_values.append(await use_christmas_bell(message, embed_data, user, user_settings))
    return any(return_values)


async def use_christmas_bell(message: discord.Message, embed_data: Dict, user: Optional[discord.User],
                                              user_settings: Optional[users.User]) -> bool:
    """Create boost reminder when using a christmas bell

    Returns
    -------
    - True if a logo reaction should be added to the message
    - False otherwise
    """
    add_reaction = False
    search_strings = [
        'was blessed with the **christmas spirit**', #English
    ]

    if any(search_string in message.content.lower() for search_string in search_strings):
        if user is None:
            user_name_match = re.search(regex.NAME_FROM_MESSAGE_START, message.content)
            user_name = user_name_match.group(1)
            user_command_message = (
                await messages.find_message(message.channel.id, regex.COMMAND_USE_CHRISTMAS_BELL,
                                            user_name=user_name)
            )
            user = user_command_message.author
        if user_settings is None:
            try:
                user_settings: users.User = await users.get_user(user.id)
            except exceptions.FirstTimeUserError:
                return add_reaction
        if not user_settings.bot_enabled or not user_settings.reminder_boosts.enabled: return add_reaction
        user_command = await functions.get_game_command(user_settings, 'boosts')
        reminder_message = (
            user_settings.reminder_boosts.message
            .replace('{boost_emoji}', emojis.PRESENT)
            .replace('{boost_name}', 'christmas spirit')
            .replace('{command}', user_command)
            .replace('  ', ' ')
        )
        time_left = timedelta(hours=4)
        reminder: reminders.Reminder = (
                await reminders.insert_user_reminder(user.id, 'boost-christmas-spirit', time_left,
                                                        message.channel.id, reminder_message)
            )
        if user_settings.reactions_enabled: add_reaction = True
    return add_reaction