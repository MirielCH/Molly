# minievent.py

from datetime import timedelta
import re
from typing import Dict, Optional

import discord

from cache import messages
from database import reminders, users
from database import settings as settings_db
from resources import emojis, exceptions, functions, regex, strings


async def process_message(bot: discord.Bot, message: discord.Message, embed_data: Dict, user: Optional[discord.User],
                          user_settings: Optional[users.User]) -> bool:
    """Processes the message for all /use related actions.

    Returns
    -------
    - True if a logo reaction should be added to the message
    - False otherwise
    """
    return_values = []
    return_values.append(await create_boost_reminder_from_shop(message, user, user_settings))
    return_values.append(await update_minievent_multiplier(embed_data))
    return any(return_values)


async def create_boost_reminder_from_shop(message: discord.Message, user: Optional[discord.User],
                                          user_settings: Optional[users.User]) -> bool:
    """Creates reminder when buying the mini boost

    Returns
    -------
    - True if a logo reaction should be added to the message
    - False otherwise
    """
    add_reaction = False
    search_strings = [
        'successfully bought', #English
    ]
    if (any(search_string in message.content.lower() for search_string in search_strings)
        and 'miniidlons' in message.content.lower()):
        if user is None:
            user_command_message = (
                await messages.find_message(message.channel.id, regex.COMMAND_MINIEVENT_BUY)
            )
            user = user_command_message.author
        if user_settings is None:
            try:
                user_settings: users.User = await users.get_user(user.id)
            except exceptions.FirstTimeUserError:
                return add_reaction

        if not user_settings.bot_enabled or not user_settings.reminder_boosts.enabled: return add_reaction
        activities_time_left = {
            'mini-boost': timedelta(hours=4),
        }
        boost_name_match = re.search(r'`(.+?)`', message.content.lower())
        boost_name = boost_name_match.group(1)
        activity = boost_name.replace(' ','-')
        if activity in strings.ACTIVITIES_BOOSTS_ALIASES: activity = strings.ACTIVITIES_BOOSTS_ALIASES[activity]
        boost_emoji = emojis.BOOSTS_EMOJIS.get(activity, '')
        if activity not in activities_time_left: return add_reaction
        time_left = activities_time_left[activity]
        user_command = await functions.get_game_command(user_settings, 'boosts')
        reminder_message = (
            user_settings.reminder_boosts.message
            .replace('{boost_emoji}', boost_emoji)
            .replace('{boost_name}', boost_name)
            .replace('{command}', user_command)
            .replace('  ', ' ')
        )
        reminder: reminders.Reminder = (
            await reminders.insert_user_reminder(user.id, f'boost-{activity}', time_left,
                                                    message.channel.id, reminder_message)
        )
        if user_settings.reactions_enabled: add_reaction = True
        return add_reaction

    
async def update_minievent_multiplier(embed_data: Dict) -> bool:
    """Updates the multiplier if necessary depending on the active mini event

    Returns
    -------
    - True if a logo reaction should be added to the message
    - False otherwise
    """
    search_strings = [
        'mini events happen 2 times per month', #English
    ]
    if any(search_string in embed_data['field1']['value'].lower() for search_string in search_strings):
        new_multiplier = 1.2 if 'energy fest' in embed_data['description'].lower() else 1.0
        all_settings = await settings_db.get_settings()
        if float(all_settings['minievent_energy_multiplier']) != new_multiplier:
            await settings_db.update_setting('minievent_energy_multiplier', str(new_multiplier))

    return False