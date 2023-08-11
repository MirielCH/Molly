# raid.py

from decimal import Decimal, ROUND_HALF_UP
import re
from typing import Dict, Optional

import discord
from discord import utils

from cache import messages
from database import users, tracking, workers
from resources import emojis, exceptions, regex, strings


async def process_message(message: discord.Message, embed_data: Dict, user: Optional[discord.User],
                          user_settings: Optional[users.User]) -> bool:
    """Processes the message for all raid related actions.

    Returns
    -------
    - True if a logo reaction should be added to the message
    - False otherwise
    """
    return_values = []
    return_values.append(await call_raid_helper(message, embed_data, user, user_settings))
    return_values.append(await track_raid(message, embed_data, user, user_settings))
    return any(return_values)


async def call_raid_helper(message: discord.Message, embed_data: Dict, user: Optional[discord.User],
                           user_settings: Optional[users.User]) -> bool:
    """Calls the raid helper

    Returns
    -------
    - True if a logo reaction should be added to the message
    - False otherwise
    """
    add_reaction = False
    search_strings = [
        'farms will be raided in order', #English
    ]
    if (any(search_string in embed_data['footer']['text'].lower() for search_string in search_strings)
        and 'raidpoints' in embed_data['field0']['name']):
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
                        await messages.find_message(message.channel.id, regex.COMMAND_RAID, user_name=user_name)
                    )
                    user = user_command_message.author
        if user_settings is None:
            try:
                user_settings: users.User = await users.get_user(user.id)
            except exceptions.FirstTimeUserError:
                return add_reaction
        if not user_settings.bot_enabled or not user_settings.helper_raid_enabled: return add_reaction
        enemies = {}
        field_enemies = ''
        for line in embed_data['field0']['value'].split('\n'):
            if 'none' in line.lower():
                 enemy_emoji = emojis.NONE
                 enemy_power = 0
            else:
                enemy_data_match = re.search(r'<a:(.+?)worker.+lv(\d+) \|.+`(\d+)/(\d+)`', line.lower())
                enemy_type = enemy_data_match.group(1)
                enemy_level = int(re.sub('\D','',enemy_data_match.group(2)))
                enemy_hp_current = int(enemy_data_match.group(3))
                enemy_hp_max = int(enemy_data_match.group(4))
                enemy_power = (
                    (strings.WORKER_STATS[enemy_type]['speed'] + strings.WORKER_STATS[enemy_type]['strength'] + strings.WORKER_STATS[enemy_type]['intelligence'])
                    * (1 + (strings.WORKER_TYPES.index(enemy_type) + 1) / 4) * (1 + enemy_level / 2.5)
                )
                enemy_power = int(Decimal(enemy_power).quantize(Decimal(1), rounding=ROUND_HALF_UP))
                enemies[enemy_type] = {
                    'level': enemy_level,
                    'power': enemy_power,
                    'hp_current': enemy_hp_current,
                    'hp_max': enemy_hp_max
                }
                enemy_emoji = getattr(emojis, f'WORKER_{enemy_type}'.upper(), emojis.WARNING)
            field_enemies = (
                f'{field_enemies}\n'
                f'{enemy_emoji} - **{enemy_power}** {emojis.WORKER_POWER}'
            )
        user_workers = await workers.get_user_workers(user.id)
        field_workers = ''
        for worker_type in strings.WORKER_TYPES:
            for user_worker in user_workers:
                if user_worker.worker_name == worker_type:
                    worker = user_worker
                    break
            worker_power = round(
                ((strings.WORKER_STATS[worker.worker_name]['speed'] + strings.WORKER_STATS[worker.worker_name]['strength']
                  + strings.WORKER_STATS[worker.worker_name]['intelligence']))
                * (1 + (strings.WORKER_TYPES.index(worker.worker_name) + 1) / 4) * (1 + worker.worker_level / 2.5)
            )
            worker_emoji = getattr(emojis, f'WORKER_{worker.worker_name}'.upper(), emojis.WARNING)
            field_workers = (
                f'{field_workers}\n'
                f'{worker_emoji} - **{worker_power}** {emojis.WORKER_POWER}'
            )
        embed = discord.Embed()
        embed.add_field(
            name = 'Your workers',
            value = field_workers.strip()
        )
        embed.add_field(
            name = 'Your enemies',
            value = field_enemies.strip()
        )
        await message.reply(embed=embed)


async def track_raid(message: discord.Message, embed_data: Dict, user: Optional[discord.User],
                     user_settings: Optional[users.User]) -> bool:
    """Tracks raids

    Returns
    -------
    - True if a logo reaction should be added to the message
    - False otherwise
    """
    search_strings = [
        'estimated raid worth', #English
    ]
    search_strings_excluded = [
        '�',
        ':trident:',
    ]
    if (any(search_string in embed_data['description'].lower() for search_string in search_strings)
        and all(search_string not in embed_data['field1']['value'] for search_string in search_strings_excluded)):
        user_name_amount_match = re.search(r'^\*\*(.+?)\*\*: (.+?) <:', embed_data['field1']['value'])
        user_name, amount = user_name_amount_match.groups()
        if user is None:
            user_command_message = (
                await messages.find_message(message.channel.id, regex.COMMAND_RAID, user_name=user_name)
            )
            user = user_command_message.author
        if user_settings is None:
            try:
                user_settings: users.User = await users.get_user(user.id)
            except exceptions.FirstTimeUserError:
                return False
        if not user_settings.tracking_enabled or not user_settings.bot_enabled: return False
        current_time = utils.utcnow().replace(microsecond=0)
        amount = int(amount)
        if amount < 0:
            amount *= -1
            item = 'raid-points-lost'
        else:
            item = 'raid-points-gained'
        await tracking.insert_log_entry(user.id, message.guild.id, item, current_time, amount)
    return False