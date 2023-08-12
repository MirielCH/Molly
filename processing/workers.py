# workers.py

import re
from typing import Dict, Optional

import discord
from discord import utils

from cache import messages
from database import clans, upgrades, users, workers, tracking, workers
from resources import exceptions, functions, regex, strings


async def process_message(bot: discord.Bot, message: discord.Message, embed_data: Dict, user: Optional[discord.User],
                          user_settings: Optional[users.User]) -> bool:
    """Processes the message for all worker related commands and events.

    Returns
    -------
    - True if a logo reaction should be added to the message
    - False otherwise
    """
    return_values = []
    return_values.append(await track_worker_hire_event(message, embed_data, user, user_settings))
    return_values.append(await track_worker_roll(message, embed_data, user, user_settings))
    return_values.append(await track_worker_stats(message, embed_data, user, user_settings))
    return any(return_values)


async def track_worker_hire_event(message: discord.Message, embed_data: Dict, user: Optional[discord.User],
                            user_settings: Optional[users.User]) -> bool:
    """Tracks worker hire

    Returns
    -------
    - True if a logo reaction should be added to the message
    - False otherwise
    """
    add_reaction = False
    search_strings_1 = [
        'hired the', #English
    ]
    search_strings_2 = [
        'worker**!', #English
    ]
    if (any(search_string in embed_data['field0']['name'].lower() for search_string in search_strings_1)
        and any(search_string in embed_data['field0']['name'].lower() for search_string in search_strings_2)):
        user_name_match = re.search(r'^(.+?) hired', embed_data['field0']['name'].lower())
        guild_members = await functions.get_guild_member_by_name(message.guild, user_name_match.group(1))
        if len(guild_members) > 1: return add_reaction
        user = guild_members[0]
        if user_settings is None:
            try:
                user_settings: users.User = await users.get_user(user.id)
            except exceptions.FirstTimeUserError:
                return False
        try:
            clan_settings: clans.Clan = await clans.get_clan_by_member_id(user.id)
        except exceptions.NoDataFoundError:
            clan_settings = None
        helper_teamraid_enabled = getattr(clan_settings, 'helper_teamraid_enabled', True)
        if (not user_settings.helper_raid_enabled and not helper_teamraid_enabled) or not user_settings.bot_enabled:
            return False
        worker_name_match = re.search(r'<a:(.+?)worker:', embed_data['field0']['name'].lower())
        worker_name = worker_name_match.group(1)
        try:
            user_worker: workers.UserWorker = await workers.get_user_worker(user.id, worker_name)
            try:
                worker_level: workers.WorkerLevel = await workers.get_worker_level(level=user_worker.worker_level + 1)
                if user_worker.worker_amount + 1 >= worker_level.workers_required:
                    await user_worker.update(worker_amount=0, worker_level=worker_level.level)
                else:
                    await user_worker.update(worker_amount=user_worker.worker_amount + 1)
            except exceptions.NoDataFoundError:
                await user_worker.update(worker_amount=user_worker.worker_amount + 1)
        except exceptions.NoDataFoundError:
            return add_reaction
    return False


async def track_worker_roll(message: discord.Message, embed_data: Dict, user: Optional[discord.User],
                            user_settings: Optional[users.User]) -> bool:
    """Tracks worker rolls

    Returns
    -------
    - True if a logo reaction should be added to the message
    - False otherwise
    """
    add_reaction = False
    search_strings = [
        '— worker roll', #All languages
    ]
    if any(search_string in embed_data['author']['name'].lower() for search_string in search_strings):
        if user is None:
            if embed_data['embed_user'] is not None:
                user = embed_data['embed_user']
                user_settings = embed_data['embed_user_settings']
            else:
                user_id_match = re.search(regex.USER_ID_FROM_ICON_URL, embed_data['author']['icon_url'])
                if user_id_match:
                    user_id = int(user_id_match.group(1))
                    user = message.guild.get_member(user_id)
                else:
                    user_name_match = re.search(regex.USERNAME_FROM_EMBED_AUTHOR, embed_data['author']['name'])
                    user_name = user_name_match.group(1)
                    user_command_message = (
                        await messages.find_message(message.channel.id, regex.COMMAND_WORKER_HIRE, user_name=user_name)
                    )
                    user = user_command_message.author
        if user_settings is None:
            try:
                user_settings: users.User = await users.get_user(user.id)
            except exceptions.FirstTimeUserError:
                return False
        try:
            clan_settings: clans.Clan = await clans.get_clan_by_member_id(user.id)
        except exceptions.NoDataFoundError:
            clan_settings = None
        helper_teamraid_enabled = getattr(clan_settings, 'helper_teamraid_enabled', True)
        if ((not user_settings.tracking_enabled and not user_settings.helper_raid_enabled and not helper_teamraid_enabled)
            or not user_settings.bot_enabled): return False
        # Update user workers
        if user_settings.helper_raid_enabled:
            worker_name_match = re.search(r'<a:(.+?)worker:', embed_data['field0']['name'].lower())
            worker_data_match = re.search(r'`\[([0-9,]+)/([0-9,]+)]`', embed_data['field0']['name'].lower())
            worker_name = worker_name_match.group(1)
            amount = int(re.sub(r'\D','', worker_data_match.group(1)))
            workers_required = int(re.sub(r'\D','', worker_data_match.group(2)))
            try:
                user_worker: workers.UserWorker = await workers.get_user_worker(user.id, worker_name)
            except exceptions.NoDataFoundError:
                user_worker = None
            if user_worker is not None:
                if amount > 0:
                    await user_worker.update(worker_amount=amount)
                else:
                    try:
                        worker_level: workers.WorkerLevel = await workers.get_worker_level(workers_required=workers_required)
                        level = worker_level.level - 1
                        await user_worker.update(worker_level=level, worker_amount=0)
                    except exceptions.NoDataFoundError:
                        pass
        # Update worker roll tracking log
        if user_settings.tracking_enabled:
            item = None
            for worker_type in strings.WORKER_TYPES:
                if worker_type in embed_data['field0']['name'].lower():
                    item = f'worker-{worker_type}'
            current_time = utils.utcnow().replace(microsecond=0)
            if item is not None:
                await tracking.insert_log_entry(user.id, message.guild.id, item, current_time)
    return False


async def track_worker_stats(message: discord.Message, embed_data: Dict, user: Optional[discord.User],
                                  user_settings: Optional[users.User]) -> bool:
    """Tacks workers from the worker stats overview embed

    Returns
    -------
    - True if a logo reaction should be added to the message
    - False otherwise
    """
    add_reaction = False
    search_strings = [
        '— workers', #English
    ]
    if any(search_string in embed_data['author']['name'].lower() for search_string in search_strings):
        if user is None:
            if embed_data['embed_user'] is not None:
                user = embed_data['embed_user']
                user_settings = embed_data['embed_user_settings']
            else:
                user_id_match = re.search(regex.USER_ID_FROM_ICON_URL, embed_data['author']['icon_url'])
                if user_id_match:
                    user_id = int(user_id_match.group(1))
                    user = message.guild.get_member(user_id)
                else:
                    user_name_match = re.search(regex.USERNAME_FROM_EMBED_AUTHOR, embed_data['author']['name'])
                    user_name = user_name_match.group(1)
                    user_command_message = (
                        await messages.find_message(message.channel.id, regex.COMMAND_WORKER_STATS, user_name=user_name)
                    )
                    user = user_command_message.author
        try:
            user_settings: users.User = await users.get_user(user.id)
        except exceptions.FirstTimeUserError:
            return add_reaction
        try:
            clan_settings: clans.Clan = await clans.get_clan_by_member_id(user.id)
        except exceptions.NoDataFoundError:
            clan_settings = None
        helper_teamraid_enabled = getattr(clan_settings, 'helper_teamraid_enabled', True)
        if not user_settings.bot_enabled or (not user_settings.helper_raid_enabled and not helper_teamraid_enabled):
            return add_reaction
        for field in message.embeds[0].fields:
            worker_name_match = re.search(r'<a:(.+?)worker:', field.name.lower())
            worker_data_match = re.search(r'level\*\*: ([0-9,]+) `\[([0-9,]+)/([0-9,]+)]`', field.value.lower())
            worker_name = worker_name_match.group(1)
            level = int(re.sub(r'\D','', worker_data_match.group(1)))
            amount = int(re.sub(r'\D','', worker_data_match.group(2)))
            workers_required = int(re.sub(r'\D','', worker_data_match.group(3)))
            try:
                user_worker = await workers.get_user_worker(user.id, worker_name)
                await user_worker.update(worker_level=level, worker_amount=amount)
            except exceptions.NoDataFoundError:
                user_worker = await workers.insert_user_worker(user.id, worker_name, level, amount)
            try:
                worker_level = await workers.get_worker_level(level + 1)
                if worker_level.workers_required != workers_required:
                    await worker_level.update(workers_required=workers_required)
            except exceptions.NoDataFoundError:
                worker_level = await workers.insert_worker_level(level, workers_required)
    return add_reaction


async def track_upgrade(message: discord.Message, user: Optional[discord.User]) -> bool:
    """Tacks upgrades from the upgrade message

    Returns
    -------
    - True if a logo reaction should be added to the message
    - False otherwise
    """
    add_reaction = False
    search_strings = [
        '` upgraded to level ', #English
    ]
    if any(search_string in message.content.lower() for search_string in search_strings):
        if user is None:
            user = message.mentions[0]
        try:
            user_settings: users.User = await users.get_user(user.id)
        except exceptions.FirstTimeUserError:
            return add_reaction
        if not user_settings.bot_enabled or not user_settings.helper_context_enabled: return add_reaction
        name_level_match = re.search(r'\d+> `(.+?)` .+level\s(\d+)\s', message.content.lower())
        name = name_level_match.group(1)
        level = int(name_level_match.group(2))
        try:
            upgrade: upgrades.Upgrade = await upgrades.get_upgrade(user.id, name)
            await upgrade.update(level=level)
        except exceptions.NoDataFoundError:
            return
        if user_settings.reactions_enabled: add_reaction = True
    return add_reaction