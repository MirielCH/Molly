# clan.py

from datetime import timedelta
import random
import re
from typing import Dict, Optional

import discord
from discord import utils

from cache import messages
from database import clans, reminders, users
from resources import exceptions, functions, regex, strings


async def process_message(bot: discord.Bot, message: discord.Message, embed_data: Dict, user: Optional[discord.User] = None,
                          user_settings: Optional[users.User] = None, clan_settings: Optional[clans.Clan] = None) -> bool:
    """Processes the message for all clan related actions.

    Returns
    -------
    - True if a logo reaction should be added to the message
    - False otherwise
    """
    return_values = []
    return_values.append(await create_clan_reminder(message, embed_data, clan_settings))
    return_values.append(await update_clan(message, embed_data, user, user_settings))
    return any(return_values)


async def create_clan_reminder(message: discord.Message, embed_data: Dict, clan_settings: Optional[clans.Clan]) -> bool:
    """Creates clan reminder from clan overview

    Returns
    -------
    - True if a logo reaction should be added to the message
    - False otherwise
    """
    add_reaction = False
    search_strings = [
        'your guild was raided', #English
    ]
    if any(search_string in embed_data['footer']['text'].lower() for search_string in search_strings):
        if clan_settings is None:
            try:
                clan_settings: clans.Clan = await clans.get_clan_by_clan_name(embed_data['field0']['name'])
            except exceptions.NoDataFoundError:
                return add_reaction
        if not clan_settings.reminder_enabled: return add_reaction
        if '✅' in embed_data['field0']['value']: return add_reaction
        clan_command = strings.SLASH_COMMANDS['teamraid']
        current_time = utils.utcnow()
        midnight_today = utils.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        end_time = midnight_today + timedelta(days=1, seconds=random.randint(60, 300))
        time_left = end_time - current_time
        if time_left < timedelta(0): return add_reaction
        reminder_message = clan_settings.reminder_message.replace('{command}', clan_command)
        reminder: reminders.Reminder = (
            await reminders.insert_clan_reminder(clan_settings.clan_name, time_left, reminder_message)
        )
        if reminder.record_exists: add_reaction = True
    return add_reaction


async def update_clan(message: discord.Message, embed_data: Dict, user: Optional[discord.User],
                      user_settings: Optional[users.User]) -> bool:
    """Updates the guild from /guild list

    Returns
    -------
    - True if a logo reaction should be added to the message
    - False otherwise
    """
    add_reaction = False
    search_strings_field_name = [
        'members', #English
    ]
    search_strings_footer = [
        'owner:', #English
    ]
    if (any(search_string in embed_data['field0']['name'].lower() for search_string in search_strings_field_name)
        and any(search_string in embed_data['footer']['text'].lower() for search_string in search_strings_footer)):
        if user is None:
            if embed_data['embed_user'] is not None:
                user = embed_data['embed_user']
                user_settings = embed_data['embed_user_settings']
            else:
                user_command_message = (
                    await messages.find_message(message.channel.id, regex.COMMAND_CLAN_LIST)
                )
                user = user_command_message.author
        if user_settings is None:
            try:
                user_settings: users.User = await users.get_user(user.id)
            except exceptions.FirstTimeUserError:
                return add_reaction
        if not user_settings.bot_enabled: return add_reaction
        clan_name_match = re.search(r'^\*\*(.+?)\*\* members', embed_data['field0']['name'])
        clan_name = clan_name_match.group(1)
        leader_match = re.search(r'Owner: (.+?)$', embed_data['footer']['text'])
        leader_id_or_name = leader_match.group(1)
        if leader_id_or_name.isnumeric():
            leader_id = int(leader_id_or_name)
        else:
            guild_members = await functions.get_guild_member_by_name(message.guild, leader_id_or_name)
            leader_id = guild_members[0].id
        clan_member_ids = []
        clan_members = f"{embed_data['field0']['value']}\n{embed_data['field1']['value']}".strip()
        for line in clan_members.split('\n'):
            user_name_match = re.search(r'^\*\*(.+?)\*\*$', line)
            if user_name_match:
                guild_members = await functions.get_guild_member_by_name(message.guild, user_name_match.group(1))
                clan_member_ids.append(guild_members[0].id)
            else:
                user_id_match = re.search(r'^ID: \*\*(\d+?)\*\*$', line)
                clan_member_ids.append(int(user_id_match.group(1)))
        try:
            clan_settings: clans.Clan = await clans.get_clan_by_leader_id(leader_id)        
            if clan_settings.clan_name != clan_name:
                if sorted(clan_settings.member_ids) == sorted(tuple(clan_member_ids)):
                    await clan_settings.update(clan_name=clan_name)
                    try:
                        reminder: reminders.Reminder = await reminders.get_clan_reminder(clan_settings.clan_name)
                        await reminder.update(clan_name=clan_name)
                    except exceptions.NoDataFoundError:
                        pass
                else:
                    try:
                        reminder: reminders.Reminder = await reminders.get_clan_reminder(clan_settings.clan_name)
                        await reminder.delete()
                    except exceptions.NoDataFoundError:
                        pass
                        await clan_settings.delete()
                        await message.channel.send(
                            f'<@{clan_settings.leader_id}> Found two guilds with unmatching members with you as an owner which '
                            f'is an invalid state I can\'t resolve.\n'
                            f'As a consequence I deleted the guild **{clan_settings.clan_name}** including **all settings**'
                            f'from my database and added **{clan_name}** as a new guild.\n\n'
                            f'If you renamed your guild: To prevent this from happening again, please run '
                            f'{await functions.get_game_command["guild list"]} immediately after renaming next time.'
                        )
        except exceptions.NoDataFoundError:
            pass
        try:
            clan_settings: clans.Clan = await clans.get_clan_by_clan_name(clan_name)
            await clan_settings.update(leader_id=leader_id, member_ids=clan_member_ids)
        except exceptions.NoDataFoundError:
            clan_settings: clans.Clan = await clans.insert_clan(clan_name, leader_id, clan_member_ids)

        for member_id in clan_settings.member_ids:
            if member_id == leader_id: continue
            try:
                old_clan_settings: clans.Clan = await clans.get_clan_by_leader_id(member_id)
                await old_clan_settings.delete()
                await message.channel.send(
                    f'Removed the guild **{old_clan_settings.clan_name}** because one of the members of this guild was its owner.\n'
                    f'Please tell one of the members of **{old_clan_settings.clan_name}** to register it again.'
                )
            except exceptions.NoDataFoundError:
                pass
        add_reaction = True
    return add_reaction