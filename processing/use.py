# use.py

from datetime import timedelta
import re
from typing import Dict, Optional

import discord
from discord import utils

from cache import messages
from database import clans, reminders, users
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
    return_values.append(await call_context_helper_on_energy_item(message, embed_data, user, user_settings))
    return_values.append(await create_boost_reminder(message, user))
    return_values.append(await create_energy_tank_reminder(message, user))
    return_values.append(await create_erngy_clover_reminder(message, user))
    return_values.append(await track_time_items(message, user))
    return_values.append(await update_clan_name_on_name_changer(message, user, user_settings))
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
        energy_amount = int(re.sub(r'\D','', energy_amount_match.group(1)))
        try:
            await functions.change_user_energy(user_settings, energy_amount)
            if user_settings.reactions_enabled: add_reaction = True
        except exceptions.EnergyFullTimeOutdatedError:
            await message.reply(strings.MSG_ENERGY_OUTDATED.format(user=user.display_name,
                                                                   cmd_profile=strings.SLASH_COMMANDS["profile"]))
        except exceptions.EnergyFullTimeNoneError:
            pass
    return add_reaction


async def create_boost_reminder(message: discord.Message, user: discord.User) -> bool:
    """Creates reminders when using boosts

    Returns
    -------
    - True if a logo reaction should be added to the message
    - False otherwise
    """
    add_reaction = False
    search_strings = [
        'got a new `boost`',
    ]
    if any(search_string in message.content.lower() for search_string in search_strings):
        if user is None:
            user_name_match = re.search(regex.NAME_FROM_MESSAGE_START, message.content.lower())
            user_name = user_name_match.group(1)
            user_command_message = (
                await messages.find_message(message.channel.id, regex.COMMAND_USE_BOOST, user_name=user_name)
            )
            user = user_command_message.author
        try:
            user_settings: users.User = await users.get_user(user.id)
        except exceptions.FirstTimeUserError:
            return add_reaction
        if not user_settings.bot_enabled or not user_settings.reminder_boosts.enabled: return add_reaction
        activities_time_left = {
            'fragrance': timedelta(days=1),
            'party-popper': timedelta(hours=1),
            'mega-boost': timedelta(days=30),
            'worger': timedelta(hours=4),
        }
        boost_name_match = re.search(r' \*\*(.+?)\*\*\.\.\.', message.content.lower())
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


async def create_energy_tank_reminder(message: discord.Message, user: discord.User) -> bool:
    """Creates reminders when using an energy tank

    Returns
    -------
    - True if a logo reaction should be added to the message
    - False otherwise
    """
    add_reaction = False
    search_strings = [
        'got +10000 max energy',
    ]
    if any(search_string in message.content.lower() for search_string in search_strings):
        if user is None:
            user_name_match = re.search(regex.NAME_FROM_MESSAGE_START, message.content.lower())
            user_name = user_name_match.group(1)
            user_command_message = (
                await messages.find_message(message.channel.id, regex.COMMAND_USE_ENERGY_TANK, user_name=user_name)
            )
            user = user_command_message.author
        try:
            user_settings: users.User = await users.get_user(user.id)
        except exceptions.FirstTimeUserError:
            return add_reaction
        if not user_settings.bot_enabled or not user_settings.reminder_boosts.enabled: return add_reaction
        boost_emoji = emojis.BOOSTS_EMOJIS.get('energy-tank', '')
        user_command = await functions.get_game_command(user_settings, 'boosts')
        reminder_message = (
            user_settings.reminder_boosts.message
            .replace('{boost_emoji}', boost_emoji)
            .replace('{boost_name}', 'energy tank')
            .replace('{command}', user_command)
            .replace('  ', ' ')
        )
        reminder: reminders.Reminder = (
            await reminders.insert_user_reminder(user.id, f'boost-energy-tank', timedelta(days=3),
                                                    message.channel.id, reminder_message)
        )
        current_time = utils.utcnow()
        await user_settings.update(energy_max=user_settings.energy_max + 10_000, energy_full_time=current_time)
        try:
            energy_reminder: reminders.Reminder = await reminders.get_user_reminder(user.id, 'energy')
            await energy_reminder.delete()
        except exceptions.NoDataFoundError:
            pass
        if user_settings.reactions_enabled: add_reaction = True
    return add_reaction


async def create_erngy_clover_reminder(message: discord.Message, user: discord.User) -> bool:
    """Creates reminders when using an erngy clover

    Returns
    -------
    - True if a logo reaction should be added to the message
    - False otherwise
    """
    add_reaction = False
    search_strings = [
        'erngy clover boost #',
    ]
    if any(search_string in message.content.lower() for search_string in search_strings):
        if user is None:
            user_name_match = re.search(regex.NAME_FROM_MESSAGE_START, message.content.lower())
            user_name = user_name_match.group(1)
            user_command_message = (
                await messages.find_message(message.channel.id, regex.COMMAND_USE_ERNGY_CLOVER, user_name=user_name)
            )
            user = user_command_message.author
        try:
            user_settings: users.User = await users.get_user(user.id)
        except exceptions.FirstTimeUserError:
            return add_reaction
        if not user_settings.bot_enabled or not user_settings.reminder_boosts.enabled: return add_reaction
        tiers = {
            1: 'i',
            2: 'ii',
            3: 'iii',
            4: 'iv',
        }
        times = {
            1: timedelta(hours=6),
            2: timedelta(hours=8),
            3: timedelta(hours=10),
            4: timedelta(hours=12),
        }
        tier_match = re.search(r'#(\d)\n', message.content.lower())
        tier = int(tier_match.group(1))
        activity = f'erngy-clover-{tiers[tier]}'
        boost_emoji = emojis.BOOSTS_EMOJIS.get(activity, '')
        user_command = await functions.get_game_command(user_settings, 'boosts')
        reminder_message = (
            user_settings.reminder_boosts.message
            .replace('{boost_emoji}', boost_emoji)
            .replace('{boost_name}', activity)
            .replace('{command}', user_command)
            .replace('  ', ' ')
        )
        reminder: reminders.Reminder = (
            await reminders.insert_user_reminder(user.id, f'boost-{activity}', times[tier],
                                                    message.channel.id, reminder_message)
        )
        if user_settings.reactions_enabled: add_reaction = True
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
        'timedilator',
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
            items_used = item_time_left.total_seconds() // 7_200
            kwargs['time_speeders_used'] = user_settings.time_speeders_used + items_used
        elif 'timedilator' in message.content.lower():
            items_used = item_time_left.total_seconds() // 28_800
            kwargs['time_dilators_used'] = user_settings.time_dilators_used + items_used
        else:
            items_used = item_time_left.total_seconds() // 14_400
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


async def update_clan_name_on_name_changer(message: discord.Message, user: Optional[discord.User],
                                           user_settings: Optional[users.User]) -> bool:
    """Update clan name when clan leader uses a name changer

    Returns
    -------
    - True if a logo reaction should be added to the message
    - False otherwise
    """
    add_reaction = False
    search_strings = [
        'guild name set to ', #English
    ]

    if any(search_string in message.content.lower() for search_string in search_strings):
        if user is None:
            user_name_match = re.search(regex.NAME_FROM_MESSAGE_START, message.content)
            user_name = user_name_match.group(1)
            user_command_message = (
                await messages.find_message(message.channel.id, regex.COMMAND_USE_GUILD_NAME_CHANGER, user_name=user_name)
            )
            user = user_command_message.author
        if user_settings is None:
            try:
                user_settings: users.User = await users.get_user(user.id)
            except exceptions.FirstTimeUserError:
                return add_reaction
        if not user_settings.bot_enabled: return add_reaction
        try:
            clan_settings = await clans.get_clan_by_leader_id(user.id)
        except exceptions.NoDataFoundError:
            return
        new_clan_name_match = re.search(r'set to (.+?)$', message.content)
        new_clan_name = new_clan_name_match.group(1)
        for clan_member in clan_settings.members:
            await clans.update_clan_member(clan_member.user_id, clan_name=new_clan_name)
        await clan_settings.update(clan_name=new_clan_name)
        if user_settings.reactions_enabled: add_reaction = True
    return add_reaction