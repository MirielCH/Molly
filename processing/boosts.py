# boosts.py

from datetime import timedelta
import re
from typing import Dict, Optional

import discord
from discord import utils

from cache import messages
from database import clans, reminders, upgrades, users
from resources import emojis, exceptions, functions, regex, settings, strings, views


async def process_message(bot: discord.Bot, message: discord.Message, embed_data: Dict, user: Optional[discord.User],
                          user_settings: Optional[users.User]) -> bool:
    """Processes the message for all boost related actions.

    Returns
    -------
    - True if a logo reaction should be added to the message
    - False otherwise
    """
    return_values = []
    return_values.append(await create_reminders_from_boosts(bot, message, embed_data, user, user_settings))
    return any(return_values)


async def create_reminders_from_boosts(bot: discord.Bot, message: discord.Message, embed_data: Dict,
                                       user: Optional[discord.User],
                                       user_settings: Optional[users.User]) -> bool:
    """• Update idluck count in the database
    • Show profile timers helper

    Returns
    -------
    - True if a logo reaction should be added to the message
    - False otherwise
    """
    add_reaction = False
    search_strings = [
        'these are your active boosts', #English
    ]
    if any(search_string in embed_data['description'].lower() for search_string in search_strings):
        if user is None:
            user_command_message = (
                await messages.find_message(message.channel.id, regex.COMMAND_BOOSTS)
            )
            if user_command_message is None: return add_reaction
            user = user_command_message.author
        if user_settings is None:
            try:
                user_settings: users.User = await users.get_user(user.id)
            except exceptions.FirstTimeUserError:
                return add_reaction
        if not user_settings.bot_enabled or not user_settings.reminder_boosts.enabled: return add_reaction
        boost_fields = embed_data['field0']['value']
        if len(message.embeds[0].fields) > 1 and embed_data['field1']['name'] == '':
            boost_fields = f'{boost_fields}\n{embed_data["field1"]["value"]}'
        all_boosts = list(strings.ACTIVITIES_BOOSTS[:])
        for line in boost_fields.lower().split('\n'):
            if 'none' in boost_fields.lower():
                try:
                    active_reminders = await reminders.get_active_user_reminders(user.id)
                    for active_reminder in active_reminders:
                        if active_reminder.activity in strings.ACTIVITIES_BOOSTS:
                            await active_reminder.delete()
                except exceptions.NoDataFoundError:
                    pass
                break
            active_item_match = re.search(r' \*\*(.+?)\*\*: (.+?)$', line)
            active_item_activity = active_item_match.group(1).replace(' ','-')
            if active_item_activity in strings.ACTIVITIES_BOOSTS_ALIASES:
                active_item_activity = strings.ACTIVITIES_BOOSTS_ALIASES[active_item_activity]
            if active_item_activity in all_boosts: all_boosts.remove(active_item_activity)
            active_item_emoji = emojis.BOOSTS_EMOJIS.get(active_item_activity, '')
            time_string = active_item_match.group(2)
            time_left = await functions.calculate_time_left_from_timestring(message, time_string)
            user_command = await functions.get_game_command(user_settings, 'boosts')
            if time_left < timedelta(0): return add_reaction
            reminder_message = (
                user_settings.reminder_boosts.message
                .replace('{boost_emoji}', active_item_emoji)
                .replace('{boost_name}', active_item_activity.replace('-', ' '))
                .replace('{command}', user_command)
                .replace('  ', ' ')
            )
            reminder: reminders.Reminder = (
                await reminders.insert_user_reminder(user.id, f'boost-{active_item_activity}', time_left,
                                                        message.channel.id, reminder_message)
            )
        for activity in all_boosts:
            try:
                active_reminder = await reminders.get_user_reminder(user.id, f'boost-{activity}')
                await active_reminder.delete()
            except exceptions.NoDataFoundError:
                continue
        if user_settings.reactions_enabled: add_reaction = True
    return add_reaction