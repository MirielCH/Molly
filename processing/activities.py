# activities.py

from datetime import timedelta
import re
from typing import Dict, Optional

import discord

from cache import messages
from database import reminders,  users
from resources import exceptions, functions, regex


async def process_message(bot: discord.Bot, message: discord.Message, embed_data: Dict, user: Optional[discord.User],
                          user_settings: Optional[users.User]) -> bool:
    """Processes the message for all activity list related actions.

    Returns
    -------
    - True if a logo reaction should be added to the message
    - False otherwise
    """
    return_values = []
    return_values.append(await update_reminders_from_activities_list(message, embed_data, user, user_settings))
    return any(return_values)


async def update_reminders_from_activities_list(message: discord.Message, embed_data: Dict, interaction_user: Optional[discord.User],
                                                user_settings: Optional[users.User]) -> bool:
    """Creates reminders or deletes them for all commands in the activities list

    Returns
    -------
    - True if a logo reaction should be added to the message
    - False otherwise
    """
    add_reaction = False
    search_strings = [
        '— cooldowns',
    ]
    if any(search_string in embed_data['author']['name'].lower() for search_string in search_strings):
        if interaction_user is None:
            user_command_message = (
                await messages.find_message(message.channel.id, regex.COMMAND_ACTIVITIES)
            )
            interaction_user = user_command_message.author
        if embed_data['embed_user'] is not None and embed_data['embed_user'] != interaction_user: return add_reaction
        if interaction_user.name not in embed_data['author']['name']: return
        if user_settings is None:
            try:
                user_settings: users.User = await users.get_user(interaction_user.id)
            except exceptions.FirstTimeUserError:
                return add_reaction
        if not user_settings.bot_enabled: return add_reaction
        cooldowns = []
        ready_commands = []
        if user_settings.reminder_daily.enabled:
            timestring_match = re.search(r"daily`\*\* \(\*\*(.+?)\*\*", embed_data['field0']['value'].lower())
            if timestring_match:
                user_command = await functions.get_game_command(user_settings, 'daily')
                reminder_message = user_settings.reminder_daily.message.replace('{command}', user_command)
                cooldowns.append(['daily', timestring_match.group(1).lower(), reminder_message])
            else:
                ready_commands.append('daily')
        if user_settings.reminder_vote.enabled:
            timestring_match = re.search(r"vote`\*\* \(\*\*(.+?)\*\*", embed_data['field0']['value'].lower())
            if timestring_match:
                user_command = await functions.get_game_command(user_settings, 'vote')
                reminder_message = user_settings.reminder_vote.message.replace('{command}', user_command)
                cooldowns.append(['vote', timestring_match.group(1).lower(), reminder_message])
            else:
                ready_commands.append('vote')

        for cooldown in cooldowns:
            cd_activity = cooldown[0]
            cd_timestring = cooldown[1]
            cd_message = cooldown[2]
            time_left = await functions.parse_timestring_to_timedelta(cd_timestring)
            if time_left <= timedelta(seconds=1): continue
            reminder: reminders.Reminder = (
                await reminders.insert_user_reminder(interaction_user.id, cd_activity, time_left,
                                                     message.channel.id, cd_message)
            )
        for activity in ready_commands:
            try:
                reminder: reminders.Reminder = await reminders.get_user_reminder(interaction_user.id, activity)
                await reminder.delete()
            except exceptions.NoDataFoundError:
                continue
        if user_settings.reactions_enabled: add_reaction = True
    return add_reaction