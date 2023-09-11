# workers.py

from datetime import timedelta
import re
from typing import Dict, Optional

import discord
from discord import utils

from cache import messages
from database import clans, upgrades, users, workers, tracking, workers
from resources import exceptions, functions, regex, strings


async def process_message(bot: discord.Bot, message: discord.Message, embed_data: Dict, user: Optional[discord.User],
                          user_settings: Optional[users.User], clan_settings: Optional[clans.Clan]) -> bool:
    """Processes the message for all worker related commands and events.

    Returns
    -------
    - True if a logo reaction should be added to the message
    - False otherwise
    """
    return_values = []
    return_values.append(await track_worker_hire_event(message, embed_data, user, user_settings, clan_settings))
    return_values.append(await track_worker_roll(message, embed_data, user, user_settings, clan_settings))
    return_values.append(await track_worker_stats(message, embed_data, user, user_settings, clan_settings))
    return any(return_values)


async def track_worker_hire_event(message: discord.Message, embed_data: Dict, user: Optional[discord.User],
                                  user_settings: Optional[users.User], clan_settings: Optional[clans.Clan]) -> bool:
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
        guild_members = await functions.get_guild_member_by_name(message.guild, user_name_match.group(1), False)
        if len(guild_members) != 1: return add_reaction
        user = guild_members[0]
        if user_settings is None:
            try:
                user_settings: users.User = await users.get_user(user.id)
            except exceptions.FirstTimeUserError:
                return add_reaction
        if clan_settings is None:
            try:
                clan_settings: clans.Clan = await clans.get_clan_by_member_id(user.id)
            except exceptions.NoDataFoundError:
                pass
        helper_teamraid_enabled = getattr(clan_settings, 'helper_teamraid_enabled', False)
        if (not user_settings.helper_raid_enabled and not helper_teamraid_enabled) or not user_settings.bot_enabled:
            return add_reaction
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
        if user_settings.reactions_enabled: add_reaction = True
    return add_reaction


async def track_worker_roll(message: discord.Message, embed_data: Dict, user: Optional[discord.User],
                            user_settings: Optional[users.User], clan_settings: Optional[clans.Clan]) -> bool:
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
                return add_reaction
        if clan_settings is None:
            try:
                clan_settings: clans.Clan = await clans.get_clan_by_member_id(user.id)
            except exceptions.NoDataFoundError:
                pass
        helper_teamraid_enabled = getattr(clan_settings, 'helper_teamraid_enabled', False)
        if ((not user_settings.tracking_enabled and not user_settings.helper_raid_enabled and not helper_teamraid_enabled)
            or not user_settings.bot_enabled): return add_reaction
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
        # Update energy time until full
        if user_settings.reminder_energy.enabled:
            energy_match = re.search(r':\s([0-9,]+)/([0-9,]+)$', embed_data['footer']['text'])
            energy_current = int(re.sub('\D','',energy_match.group(1)))
            energy_max = int(re.sub('\D','',energy_match.group(2)))
            energy_regen_time = await functions.get_energy_regen_time(user_settings)
            seconds_until_max = (int(energy_max) - int(energy_current)) * energy_regen_time.total_seconds()
            current_time = utils.utcnow()
            energy_full_time = current_time + timedelta(seconds=seconds_until_max)
            await user_settings.update(energy_max=energy_max, energy_full_time=energy_full_time)
            await functions.recalculate_energy_reminder(user_settings, energy_regen_time)
    return add_reaction


async def track_worker_stats(message: discord.Message, embed_data: Dict,
                             interaction_user: Optional[discord.User],
                             user_settings: Optional[users.User], clan_settings: Optional[clans.Clan]) -> bool:
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
        if interaction_user is None:
            user_name_match = re.search(regex.USERNAME_FROM_EMBED_AUTHOR, embed_data['author']['name'])
            user_name = user_name_match.group(1)
            user_command_message = (
                await messages.find_message(message.channel.id, regex.COMMAND_WORKER_STATS, user_name=user_name)
            )
            if user_command_message is None: return add_reaction
            interaction_user = user_command_message.author
        if embed_data['embed_user'] != interaction_user: return add_reaction
        try:
            user_settings: users.User = await users.get_user(interaction_user.id)
        except exceptions.FirstTimeUserError:
            return add_reaction
        if clan_settings is None:
            try:
                clan_settings: clans.Clan = await clans.get_clan_by_member_id(interaction_user.id)
            except exceptions.NoDataFoundError:
                pass
        helper_teamraid_enabled = getattr(clan_settings, 'helper_teamraid_enabled', False)
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
                user_worker = await workers.get_user_worker(interaction_user.id, worker_name)
                await user_worker.update(worker_level=level, worker_amount=amount)
            except exceptions.NoDataFoundError:
                user_worker = await workers.insert_user_worker(interaction_user.id, worker_name, level, amount)
            try:
                worker_level = await workers.get_worker_level(level + 1)
                if worker_level.workers_required != workers_required:
                    await worker_level.update(workers_required=workers_required)
            except exceptions.NoDataFoundError:
                worker_level = await workers.insert_worker_level(level, workers_required)
        if user_settings.reactions_enabled: add_reaction = True
    return add_reaction