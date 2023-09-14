# workers.py

import re
from typing import Dict, Optional

import discord

from cache import messages
from database import clans,users, workers, workers
from resources import exceptions, regex


async def process_message(bot: discord.Bot, message: discord.Message, embed_data: Dict, user: Optional[discord.User],
                          user_settings: Optional[users.User], clan_settings: Optional[clans.Clan]) -> bool:
    """Processes the message for all worker related commands and events.

    Returns
    -------
    - True if a logo reaction should be added to the message
    - False otherwise
    """
    return_values = []
    return_values.append(await track_workers_from_lootboxes(message, embed_data, user, user_settings, clan_settings))
    return any(return_values)


async def track_workers_from_lootboxes(message: discord.Message, embed_data: Dict, user: Optional[discord.User],
                                       user_settings: Optional[users.User], clan_settings: Optional[clans.Clan]) -> bool:
    """Tracks worker hire

    Returns
    -------
    - True if a logo reaction should be added to the message
    - False otherwise
    """
    add_reaction = False
    search_strings = [
        '— lootbox', #All languages
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
                    await messages.find_message(message.channel.id, regex.COMMAND_OPEN, user_name=user_name)
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
        if not user_settings.bot_enabled: return add_reaction
        for line in embed_data['field0']['value'].split('\n'):
            worker_data_match = re.search(r'^\+([0-9,]+)\s<a:(.+?)worker:', line.lower())
            if worker_data_match:
                worker_amount = int(worker_data_match.group(1))
                worker_name = worker_data_match.group(2)
                try:
                    user_worker: workers.UserWorker = await workers.get_user_worker(user.id, worker_name)
                    new_worker_level = user_worker.worker_level
                    new_worker_amount = user_worker.worker_amount + worker_amount
                    try:
                        worker_level: workers.WorkerLevel = await workers.get_worker_level(user_worker.worker_level + 1)
                        if user_worker.worker_amount + worker_amount > worker_level.workers_required:
                            new_worker_level = worker_level.level
                            new_worker_amount = user_worker.worker_amount + worker_amount - worker_level.workers_required
                    except exceptions.NoDataFoundError:
                        pass
                    await user_worker.update(worker_level=new_worker_level, worker_amount=new_worker_amount)
                except exceptions.NoDataFoundError:
                    worker_levels = await workers.get_worker_levels()
                    level = 0
                    worker_amount_left = worker_amount
                    for worker_level in worker_levels:
                        if worker_amount_left > worker_level.workers_required:
                            level += 1
                            worker_amount_left -= worker_level.workers_required
                        else:
                            break
                    await workers.insert_user_worker(user.id, worker_name, level, worker_amount_left)
        if user_settings.reactions_enabled: add_reaction = True
    return add_reaction