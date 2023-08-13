# request.py

import re
from typing import Dict, Optional

import discord

from cache import messages
from database import clans, users, workers
from resources import exceptions, functions, regex


async def process_message(bot: discord.Bot, message: discord.Message, embed_data: Dict, user: Optional[discord.User],
                          user_settings: Optional[users.User], clan_settings: Optional[clans.Clan]) -> bool:
    """Processes the message for all raid related actions.

    Returns
    -------
    - True if a logo reaction should be added to the message
    - False otherwise
    """
    return_values = []
    return_values.append(await update_workers_and_idlucks(message, embed_data, user, user_settings, clan_settings))
    return any(return_values)


async def update_workers_and_idlucks(message: discord.Message, embed_data: Dict, user: Optional[discord.User],
                                     user_settings: Optional[users.User], clan_settings: Optional[clans.Clan]) -> bool:
    """Tracks workers and idlucks from requests

    Returns
    -------
    - True if a logo reaction should be added to the message
    - False otherwise
    """
    add_reaction = False
    search_patterns = [
        r'\*\* got .+/.+worker\*\*', #English
    ]
    if await functions.get_match_from_patterns(search_patterns, embed_data['description']) is not None:
        user_name_match = re.search(regex.NAME_FROM_MESSAGE_START, embed_data['description'])
        worker_amount_name_match = re.search(r'got (\d+)/.+<a:(.+?)worker:', embed_data['description'].lower())
        supplier_idlucks_match = re.search(r'^(.+?) —.+\(\+(\d+) <', embed_data['description'].split('\n')[1].lower())
        user_name = user_name_match.group(1)
        worker_amount = int(worker_amount_name_match.group(1))
        worker_name = worker_amount_name_match.group(2)
        supplier_name = supplier_idlucks_match.group(1)
        idlucks = int(supplier_idlucks_match.group(2))
        user_command_message = (
            await messages.find_message(message.channel.id, regex.COMMAND_REQUEST, user_name=user_name)
        )
        user = user_command_message.author
        if user_settings is None:
            try:
                user_settings: users.User = await users.get_user(user.id)
            except exceptions.FirstTimeUserError:
                return add_reaction
        if not user_settings.bot_enabled: return False
        if clan_settings is None:
            try:
                clan_settings: clans.Clan = await clans.get_clan_by_member_id(user.id)
            except exceptions.NoDataFoundError:
                pass
        helper_teamraid_enabled = getattr(clan_settings, 'helper_teamraid_enabled', False)
        if (not user_settings.helper_upgrades_enabled and not user_settings.helper_raid_enabled
            and not helper_teamraid_enabled):
            return add_reaction
        guild_members = await functions.get_guild_member_by_name(message.guild, supplier_name)
        if len(guild_members) == 1:
            supplier = guild_members[0]
        else:
            supplier = None
        if supplier is not None:
            try:
                supplier_settings: users.User = await users.get_user(supplier.id)
            except exceptions.FirstTimeUserError:
                supplier_settings = None
        try:
            user_worker: workers.UserWorker = await workers.get_user_worker(user.id, worker_name)
        except:
            user_worker = None
        if user_worker is None:
            await workers.insert_user_worker(user.id, worker_name, 1, worker_amount)
            if user_settings.reactions_enabled: add_reaction = True
        else:
            new_worker_level = user_worker.worker_level
            new_worker_amount = user_worker.worker_amount + worker_amount
            try:
                worker_level: workers.WorkerLevel = await workers.get_worker_level(user_worker.worker_level + 1)
            except exceptions.NoDataFoundError:
                worker_level = None
            if worker_level is not None:
                if user_worker.worker_amount + worker_amount > worker_level.workers_required:
                    new_worker_level = worker_level.level
                    new_worker_amount = user_worker.worker_amount + worker_amount - worker_level.workers_required
            await user_worker.update(worker_level=new_worker_level, worker_amount=new_worker_amount)
            if user_settings.reactions_enabled: add_reaction = True
        if supplier_settings is not None:
            if supplier_settings.helper_raid_enabled:
                try:
                    supplier_worker: workers.UserWorker = await workers.get_user_worker(supplier.id, worker_name)
                    new_worker_level = supplier_worker.worker_level
                    new_worker_amount = supplier_worker.worker_amount - worker_amount
                    try:
                        worker_level: workers.WorkerLevel = await workers.get_worker_level(supplier_worker.worker_level)
                    except exceptions.NoDataFoundError:
                        worker_level = None
                    if worker_level is not None:
                        if supplier_worker.worker_amount - worker_amount < 0:
                            new_worker_level = supplier_worker.worker_level - 1
                            new_worker_amount = supplier_worker.worker_amount - worker_amount + worker_level.workers_required
                    await supplier_worker.update(worker_amount=new_worker_amount, worker_level=new_worker_level)
                except exceptions.NoDataFoundError:
                    pass
            if supplier_settings.helper_upgrades_enabled:
                await supplier_settings.update(idlucks=supplier_settings.idlucks + idlucks)
    return add_reaction