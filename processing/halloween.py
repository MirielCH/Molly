# halloween.py

from datetime import timedelta
import re
from typing import Dict, Optional

import discord

from cache import messages
from database import reminders, users
from resources import emojis, exceptions, functions, regex, settings, strings


async def process_message(bot: discord.Bot, message: discord.Message, embed_data: Dict, user: Optional[discord.User],
                          user_settings: Optional[users.User]) -> bool:
    """Processes the message for all halloween related actions.

    Returns
    -------
    - True if a logo reaction should be added to the message
    - False otherwise
    """
    return_values = []
    return_values.append(await process_trickortreat(message, embed_data, user, user_settings))
    return any(return_values)


async def process_trickortreat(message: discord.Message, embed_data: Dict, user: Optional[discord.User],
                                              user_settings: Optional[users.User]) -> bool:
    """Create boost reminders and update energy for trickortreat

    Returns
    -------
    - True if a logo reaction should be added to the message
    - False otherwise
    """
    add_reaction = False
    search_strings = [
        '** spooked **', #English
        '**candy apple** to **', #English
    ]

    if any(search_string in message.content.lower() for search_string in search_strings):
        search_patterns = [
            r'^\*\*(.+?)\*\* spooked \*\*(.+?)\*\*',
            r'^\*\*(.+?)\*\* gave.+to \*\*(.+?)\*\*'
        ]
        user_names_match = await functions.get_match_from_patterns(search_patterns, message.content)
        event_type = 'trick' if 'spooked' in message.content.lower() else 'treat'
        target = target_settings = None
        user_name, target_name = user_names_match.groups()
        if user is None:    
            user_command_message = (
                await messages.find_message(message.channel.id, regex.COMMAND_HAL_TRICKORTREAT)
            )
            user = user_command_message.author
            for mentioned_user in user_command_message.mentions:
                if mentioned_user.id != settings.GAME_ID:
                    target = user_command_message.mentions[0]
                    break
        if target is None:
            target_users = await functions.get_guild_member_by_name(message.guild, target_name)
            if len(target_users) == 1: target = target_users[0]
        if user_settings is None:
            try:
                user_settings: users.User = await users.get_user(user.id)
            except exceptions.FirstTimeUserError:
                pass
        if target is not None:
            try:
                target_settings: users.User = await users.get_user(target.id)
            except exceptions.FirstTimeUserError:
                if user_settings is None: return add_reaction
        user_bot_enabled = getattr(user_settings, 'bot_enabled', False)
        target_bot_enabled = getattr(target_settings, 'bot_enabled', False)
        if (not user_bot_enabled and not target_bot_enabled): return add_reaction
        if user_settings is not None:
            try:
                await functions.change_user_energy(user_settings, -20)
            except exceptions.EnergyFullTimeOutdatedError:
                await message.reply(strings.MSG_ENERGY_OUTDATED.format(user=user.display_name,
                                                                       cmd_profile=strings.SLASH_COMMANDS["profile"]))
            except exceptions.EnergyFullTimeNoneError:
                pass
            if user_settings.reminder_boosts.enabled and event_type == 'trick':
                user_boost_name_match = re.search(r'and received the \*\*(.+?)\*\*', message.content.lower())
                user_boost_name = user_boost_name_match.group(1)
                time_left = timedelta(hours=6)
                reminder_message = (
                    user_settings.reminder_boosts.message
                    .replace('{boost_emoji}', emojis.PUMPKIN_CARVED)
                    .replace('{boost_name}', user_boost_name)
                )
                reminder: reminders.Reminder = (
                    await reminders.insert_user_reminder(user.id, f'boost-{user_boost_name.replace(" ","-")}', time_left,
                                                        message.channel.id, reminder_message)
                )
            if user_settings.reactions_enabled: add_reaction = True
        if target_settings is not None:
            if event_type == 'trick':
                if target_settings.reminder_boosts.enabled:
                    time_left = timedelta(hours=6)
                    reminder_message = (
                        target_settings.reminder_boosts.message
                        .replace('{boost_emoji}', emojis.PUMPKIN)
                        .replace('{boost_name}', 'spooked')
                    )
                    reminder: reminders.Reminder = (
                        await reminders.insert_user_reminder(target.id, 'boost-spooked', time_left,
                                                            message.channel.id, reminder_message)
                    )
            else:
                try:
                    await functions.change_user_energy(target_settings, -20)
                    if target_settings.reactions_enabled: add_reaction = True
                except exceptions.EnergyFullTimeOutdatedError:
                    await message.reply(strings.MSG_ENERGY_OUTDATED.format(user=target.display_name,
                                                                           cmd_profile=strings.SLASH_COMMANDS["profile"]))
                except exceptions.EnergyFullTimeNoneError:
                    pass
            if target_settings.reactions_enabled: add_reaction = True
    return add_reaction