# clan.py

from datetime import timedelta
import random
import re
from typing import Dict, Optional

import discord
from discord import utils
import pendulum

from cache import messages
from database import clans, errors, reminders, users
from resources import exceptions, functions, logs, regex, strings


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
    return_values.append(await update_clan(bot, message, embed_data, user, user_settings))
    return_values.append(await update_guild_seals_from_contribution(bot, message, embed_data, user, user_settings))
    return_values.append(await add_joined_member_to_clan(message, embed_data, user, user_settings))
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
        player_count_match = re.search(r'players\*\*: (\d+)\/', embed_data['field0']['value'].lower())
        player_count = int(player_count_match.group(1))
        if len(clan_settings.members) != player_count:
            await message.reply(
                f'My guild member list seems to be outdated.\n'
                f'Please use {strings.SLASH_COMMANDS["guild list"]} to update it.'
            )
        if not clan_settings.reminder_enabled: return add_reaction
        if '✅' in embed_data['field0']['value']: return add_reaction
        clan_command = strings.SLASH_COMMANDS['teamraid']
        current_time = utils.utcnow()
        midnight_today = utils.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        end_time = midnight_today + timedelta(days=1, seconds=random.randint(0, 600))
        time_left = end_time - current_time + timedelta(hours=clan_settings.reminder_offset)
        if time_left < timedelta(0): return add_reaction
        reminder_message = clan_settings.reminder_message.replace('{command}', clan_command)
        reminder: reminders.Reminder = (
            await reminders.insert_clan_reminder(clan_settings.clan_name, time_left, reminder_message)
        )
        if reminder.record_exists: add_reaction = True
    return add_reaction


async def update_clan(bot: discord.Bot, message: discord.Message, embed_data: Dict, user: Optional[discord.User],
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
        try:
            leader_id = int(leader_id_or_name)
        except ValueError:
            guild_members = await functions.get_guild_member_by_name(message.guild, leader_id_or_name, False)
            try:
                leader_id = guild_members[0].id
            except Exception as error:
                await errors.log_error(f'Error while trying to find leader id. Found no guild member with name "{leader_id_or_name}".',
                                       message)
        clan_members_found = {}
        clan_members = (
            f"{embed_data['field0']['value']}\n"
            f"{embed_data['field1']['value']}\n"
            f"{embed_data['field2']['value']}\n"
            f"{embed_data['field3']['value']}\n"
            f"{embed_data['field4']['value']}\n"
            f"{embed_data['field5']['value']}"
        ).strip()
        for line in clan_members.split('\n'):
            member_data_match = re.search(r'^\*\*(.+?)\*\* - (\d+?) <', line)
            if member_data_match:
                user_name, guild_seals_contributed = member_data_match.groups()
                guild_members = await functions.get_guild_member_by_name(message.guild, user_name, False)
                clan_members_found[guild_members[0].id] = guild_seals_contributed
            else:
                member_data_match = re.search(r'^ID: \*\*(\d+?)\*\* - (\d+?) <', line)
                user_id, guild_seals_contributed = member_data_match.groups()
                clan_members_found[user_id] = guild_seals_contributed
        try:
            clan_settings: clans.Clan = await clans.get_clan_by_leader_id(leader_id)
            if clan_settings.clan_name != clan_name:
                if sorted(clan_settings.members, key= lambda x:x.user_id) == sorted(tuple(clan_members_found.keys())):
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
        guild_seals_total_old = 0
        try:
            clan_settings: clans.Clan = await clans.get_clan_by_clan_name(clan_name)
            for clan_member in clan_settings.members:
                guild_seals_total_old += clan_member.guild_seals_contributed
            await clan_settings.update(leader_id=leader_id, members=clan_members_found)
        except exceptions.NoDataFoundError:
            clan_settings: clans.Clan = await clans.insert_clan(clan_name, leader_id, clan_members_found)
        guild_seals_total_new = 0
        for clan_member in clan_settings.members:
            guild_seals_total_new += clan_member.guild_seals_contributed
            if clan_member.user_id == leader_id: continue
            try:
                old_clan_settings: clans.Clan = await clans.get_clan_by_leader_id(clan_member.user_id)
                await old_clan_settings.delete()
                await message.channel.send(
                    f'Removed the guild **{old_clan_settings.clan_name}** because one of the members of this guild was its owner.\n'
                    f'Please tell one of the members of **{old_clan_settings.clan_name}** to register it again.'
                )
            except exceptions.NoDataFoundError:
                pass
        if clan_settings.alert_contribution_enabled:
            threshold_unlocked = 0
            for index, threshold in enumerate(strings.GUILD_BUFF_THRESHOLDS):
                if guild_seals_total_old < threshold and guild_seals_total_new >= threshold:
                    threshold_unlocked = threshold
            if threshold_unlocked > 0:
                index = strings.GUILD_BUFF_THRESHOLDS.index(threshold_unlocked)
                next_monday = pendulum.now().next(pendulum.MONDAY).replace(hour=0, minute=0, second=0, microsecond=0)
                guild_buff_name = f'Guild buff {strings.NUMBERS_INTEGER_ROMAN[index + 1].upper()}'
                alert_message = (
                    clan_settings.alert_contribution_message
                    .replace('{guild_role}', f'<@&{clan_settings.reminder_role_id}>')
                    .replace('{guild_buff_name}', guild_buff_name)
                    .replace('{guild_seals_total}', str(guild_seals_total_new))
                    .replace('{guild_contribution_reset_time}', utils.format_dt(next_monday, "R"))
                )
                channel = await functions.get_discord_channel(bot, clan_settings.reminder_channel_id)
                if channel is not None:
                    allowed_mentions = discord.AllowedMentions(roles=True)
                    await channel.send(alert_message, allowed_mentions=allowed_mentions)
        add_reaction = True
    return add_reaction


async def update_guild_seals_from_contribution(bot: discord.Bot, message: discord.Message, embed_data: Dict, user: Optional[discord.User],
                                               user_settings: Optional[users.User]) -> bool:
    """Update guild seals when contributing them

    Returns
    -------
    - True if a logo reaction should be added to the message
    - False otherwise
    """
    add_reaction = False
    search_strings = [
        'successfully contributed to **', #English
    ]

    if any(search_string in message.content.lower() for search_string in search_strings):
        user = message.mentions[0]
        try:
            clan_settings = await clans.get_clan_by_member_id(user.id)
        except exceptions.NoDataFoundError:
            clan_settings = None
        if user_settings is None:
            try:
                user_settings: users.User = await users.get_user(user.id)
            except exceptions.FirstTimeUserError:
                pass
        if user_settings is None and clan_settings is None: return add_reaction
        guild_seals_match = re.search(r', ([0-9,]+) <', message.content.lower())
        guild_seals_count = int(guild_seals_match.group(1).replace(',',''))
        if clan_settings is not None:
            guild_seals_total_old = 0
            for clan_member in clan_settings.members:
                guild_seals_total_old += clan_member.guild_seals_contributed
            for clan_member in clan_settings.members:
                if clan_member.user_id == user.id:
                    guild_seals_contributed = clan_member.guild_seals_contributed + guild_seals_count
                    await clans.update_clan_member(user.id, guild_seals_contributed=guild_seals_contributed)
                    break
            if clan_settings.alert_contribution_enabled:
                guild_seals_total_new = guild_seals_total_old + guild_seals_count
                threshold_unlocked = 0
                for index, threshold in enumerate(strings.GUILD_BUFF_THRESHOLDS):
                    if guild_seals_total_old < threshold and guild_seals_total_new >= threshold:
                        threshold_unlocked = threshold
                if threshold_unlocked > 0:
                    index = strings.GUILD_BUFF_THRESHOLDS.index(threshold_unlocked)
                    next_monday = pendulum.now().next(pendulum.MONDAY).replace(hour=0, minute=0, second=0, microsecond=0)
                    guild_buff_name = f'Guild buff {strings.NUMBERS_INTEGER_ROMAN[index + 1].upper()}'
                    alert_message = (
                        clan_settings.alert_contribution_message
                        .replace('{guild_role}', f'<@&{clan_settings.reminder_role_id}>')
                        .replace('{guild_buff_name}', guild_buff_name)
                        .replace('{guild_seals_total}', str(guild_seals_total_new))
                        .replace('{guild_contribution_reset_time}', utils.format_dt(next_monday, "R"))
                    )
                    channel = await functions.get_discord_channel(bot, clan_settings.reminder_channel_id)
                    if channel is not None:
                        allowed_mentions = discord.AllowedMentions(roles=True)
                        await channel.send(alert_message, allowed_mentions=allowed_mentions)
            add_reaction = True
        if user_settings is not None:
            if not user_settings.bot_enabled: return add_reaction
            guild_seals_new = clan_member.guild_seals_contributed - guild_seals_count
            if guild_seals_new < 0: guild_seals_new = 0
            await user_settings.update(inventory_guild_seal=guild_seals_new)
            if user_settings.reactions_enabled: add_reaction = True
    return add_reaction


async def add_joined_member_to_clan(message: discord.Message, embed_data: Dict, user: Optional[discord.User],
                                    user_settings: Optional[users.User]) -> bool:
    """
    Sends a reminder when a member joins a registered clan

    Returns
    -------
    - True if a logo reaction should be added to the message
    - False otherwise
    """

    add_reaction = False
    search_strings = [
        '** joined **', #English
        'successfully kicked from **', #English
    ]

    if any(search_string in message.content.lower() for search_string in search_strings):
        clan_name_match = re.search(r' \*\*(.+?)\*\*$', message.content)
        try:
            clan_settings = await clans.get_clan_by_clan_name(clan_name_match.group(1))
        except exceptions.NoDataFoundError:
            return add_reaction
        await message.reply(
            f'Don\'t forget to use {strings.SLASH_COMMANDS["guild list"]} to update my guild data.'
        )
    return add_reaction