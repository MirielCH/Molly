# teamraid.py
"""Contains commands related to teamraids"""

from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP
import random
import re
from typing import Dict, Optional

import discord
from discord import utils

from cache import messages
from database import clans, reminders, users, workers
from resources import emojis, exceptions, functions, regex, settings, strings


async def process_message(bot: discord.Bot, message: discord.Message, embed_data: Dict, user: Optional[discord.User],
                          user_settings: Optional[users.User]) -> bool:
    """Processes the message for all tracking related actions.

    Returns
    -------
    - True if a logo reaction should be added to the message
    - False otherwise
    """
    return_values = []
    return_values.append(await call_teamraid_helper(message, embed_data, user, user_settings))
    return_values.append(await create_clan_reminder(message, embed_data))
    return any(return_values)


async def call_teamraid_helper(message: discord.Message, embed_data: Dict, user: Optional[discord.User],
                               user_settings: Optional[users.User]) -> bool:
    """Calls the teamraid helper

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
        and not 'raidpoints' in embed_data['field0']['name']):
        teamraid_users_workers = {}
        for row in message.components:
            found_workers = []
            for button in row.children:
                worker_type_match = re.search(r'^(.+?)worker', button.emoji.name.lower())
                found_workers.append(worker_type_match.group(1))
            teamraid_users_workers[button.label] = found_workers
        if user is not None:
            teamraid_users = [user,]
            for teamraid_user_name in teamraid_users_workers.keys():
                guild_members = await functions.get_guild_member_by_name(message.guild, teamraid_user_name)
                teamraid_users.append(guild_members[0])
        else:
            if embed_data['embed_user'] is not None:
                user = embed_data['embed_user']
                user_settings = embed_data['embed_user_settings']
            user_name_match = re.search(regex.USERNAME_FROM_EMBED_AUTHOR, embed_data['author']['name'])
            user_name = user_name_match.group(1)
            user_command_message = (
                await messages.find_message(message.channel.id, regex.COMMAND_TEAMRAID, user_name=user_name)
            )
            if user is None: user = user_command_message.author
            teamraid_users = [user,] + user_command_message.mentions
        try:
            clan_settings: clans.Clan = await clans.get_clan_by_member_id(user.id)
        except exceptions.NoDataFoundError: return add_reaction
        if not clan_settings.helper_teamraid_enabled: return add_reaction
        enemy_name_match = re.search(r'\*\*(.+?) farms', embed_data['field0']['name'].lower())
        enemy_name = enemy_name_match.group(1).upper()
        enemies = {}
        field_enemies = ''
        for line in embed_data['field0']['value'].split('\n'):
            enemy_data_match = re.search(r'<a:(.+?)worker.+lv(\d+) \|.+`(\d+)/(\d+)`', line.lower())
            enemy_type = enemy_data_match.group(1)
            enemy_level = int(re.sub('\D','',enemy_data_match.group(2)))
            enemy_hp_current = int(enemy_data_match.group(3))
            enemy_hp_max = int(enemy_data_match.group(4))
            enemy_power = (
                (strings.WORKER_STATS[enemy_type]['speed'] + strings.WORKER_STATS[enemy_type]['strength'] + strings.WORKER_STATS[enemy_type]['intelligence'])
                * (1 + (strings.WORKER_TYPES.index(enemy_type) + 1) / 4) * (1 + enemy_level / 2.5) * (enemy_hp_max / 100) / enemy_hp_max * enemy_hp_current
            )
            enemy_power = int(Decimal(enemy_power).quantize(Decimal(1), rounding=ROUND_HALF_UP))
            enemies[enemy_type] = {
                'level': enemy_level,
                'power': enemy_power,
                'hp_current': enemy_hp_current,
                'hp_max': enemy_hp_max
            }
            enemy_emoji = getattr(emojis, f'WORKER_{enemy_type}_A'.upper(), emojis.WARNING)
            field_enemies = (
                f'{field_enemies}\n'
                f'{enemy_emoji} - **{enemy_power}** {emojis.WORKER_POWER}'
            )
        embed = discord.Embed(color=settings.EMBED_COLOR)
        for teamraid_user in teamraid_users:
            user_workers_required = {}
            field_workers = ''
            try:
                user_settings: users.User = await users.get_user(teamraid_user.id)
                user_workers = await workers.get_user_workers(teamraid_user.id)
                for user_worker in user_workers:
                    if user_worker.worker_name in teamraid_users_workers[teamraid_user.name]:
                        user_workers_required[user_worker.worker_name] = user_worker.worker_level
            except exceptions.NoDataFoundError:
                user_settings = user_workers = None
            for worker_type in teamraid_users_workers[teamraid_user.name]:
                worker_emoji = getattr(emojis, f'WORKER_{worker_type}_A'.upper(), emojis.WARNING)
                if user_workers is None:
                    current_worker = f'{worker_emoji} - **?** {emojis.WORKER_POWER}'    
                else:
                    worker_power = round(
                        ((strings.WORKER_STATS[worker_type]['speed'] + strings.WORKER_STATS[worker_type]['strength']
                        + strings.WORKER_STATS[worker_type]['intelligence']))
                        * (1 + (strings.WORKER_TYPES.index(worker_type) + 1) / 4) * (1 + user_workers_required[worker_type] / 2.5)
                    )
                    current_worker = f'{worker_emoji} - **{worker_power}** {emojis.WORKER_POWER}'            
                field_workers = (
                    f'{field_workers}\n'
                    f'{current_worker}'
                )
            embed.add_field(
                name = teamraid_user.name,
                value = field_workers.strip()
            )
        embed.insert_field_at(
            index=0,
            name = enemy_name,
            value = f'{field_enemies.strip()}\n{emojis.BLANK}',
            inline = False
        )
        embed.insert_field_at(
            index=1,
            name = clan_settings.clan_name.upper(),
            value = '_If a worker power shows as **?**, the player is not using Molly or has not shown me their workers list._',
            inline = False
        )
        await message.reply(embed=embed)


async def create_clan_reminder(message: discord.Message, embed_data: Dict) -> bool:
    """Create clan reminder from teamraids

    Returns
    -------
    - True if a logo reaction should be added to the message
    - False otherwise
    """
    add_reaction = False
    search_strings_description = [
        'estimated raid worth', #English
    ]
    search_strings_field1 = [
        '🔱',
        ':trident:',
    ]
    if (any(search_string in embed_data['description'].lower() for search_string in search_strings_description)
        and any(search_string in embed_data['field1']['value'] for search_string in search_strings_field1)):
        clan_name_match = re.search(r'^\*\*(.+?)\*\*:', embed_data['field1']['value'])
        try:
            clan_settings: clans.Clan = await clans.get_clan_by_clan_name(clan_name_match.group(1))
        except exceptions.NoDataFoundError:
            return add_reaction
        if not clan_settings.reminder_enabled: return add_reaction
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