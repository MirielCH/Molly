# teamraid.py
"""Contains commands related to teamraids"""

import copy
from datetime import timedelta
from itertools import combinations
import random
import re
from typing import Dict, Optional, Tuple, Union

import discord
from discord import utils

from cache import messages
from database import clans, reminders, users, workers
from resources import emojis, exceptions, functions, logs, regex, settings, strings


async def process_message(bot: discord.Bot, message: discord.Message, embed_data: Dict, user: Optional[discord.User],
                          user_settings: Optional[users.User], clan_settings: Optional[clans.Clan]) -> bool:
    """Processes the message for all tracking related actions.

    Returns
    -------
    - True if a logo reaction should be added to the message
    - False otherwise
    """
    return_values = []
    return_values.append(await call_teamraid_helper(bot, message, embed_data, user, user_settings, clan_settings))
    return_values.append(await create_clan_reminder(message, embed_data, clan_settings))
    return any(return_values)


async def call_teamraid_helper(bot: discord.Bot, message: discord.Message, embed_data: Dict, user: Optional[discord.User],
                               user_settings: Optional[users.User], clan_settings: Optional[clans.Clan]) -> bool:
    """Calls the teamraid helper

    Returns
    -------
    - True if a logo reaction should be added to the message
    - False otherwise
    """
    async def read_enemy_farms(data: Union[discord.Message, discord.RawMessageUpdateEvent]) -> Dict[str, int]:
        """Returns the name and power of the enemy farms found in the teamraid embed.

        Arguments
        ---------
        message: The message with the enemy farms

        Returns
        -------
        Tuple with the enemies (Dict[enemy_name: enemy_power])
        """
        if isinstance(data, discord.Message):
            fields = []
            for field in data.embeds[0].fields:
                fields.append({'name': field.name, 'value': field.value})
        else:
            fields = data.data['embeds'][0]['fields']
        enemies_power = {}
        for field_index, field in enumerate(fields):
            if not 'farm' in field['name'].lower() and field['name'] != '': continue
            for line in field['value'].split('\n'):
                enemy_data_match = re.search(r'<a:(.+?)worker.+lv(\d+) \|.+`(\d+)/(\d+)`', line.lower())
                if not enemy_data_match and 'none' in line.lower(): continue
                enemy_type = enemy_data_match.group(1)
                enemy_level = int(re.sub(r'\D','',enemy_data_match.group(2)))
                enemy_hp_current = int(enemy_data_match.group(3))
                enemy_hp_max = int(enemy_data_match.group(4))
                enemy_power = (
                    (strings.WORKER_STATS[enemy_type]['speed'] + strings.WORKER_STATS[enemy_type]['strength']
                    + strings.WORKER_STATS[enemy_type]['intelligence'])
                    * (1 + (strings.WORKER_STATS[enemy_type]['tier']) / 2.5) * (1 + enemy_level / 1.25)
                )
                enemies_power[f'{enemy_type}{field_index}'] = (enemy_power, enemy_hp_current)
        return enemies_power

    async def get_recommended_worker(next_enemy_power_hp: Tuple[int, int],
                                     workers_still_alive: Dict[str, Dict[str, int]]) -> Dict[str, Dict[str, int]]:
        """Returns the next recommended worker.

        Returns
        -------
        Dict with the next recommended worker (Dict[user_name: Dict[enemy_name: enemy_power]])
        """
        recommended_worker = {}
        next_enemy_power, next_enemy_hp = next_enemy_power_hp
        if len(list(workers_still_alive.keys())) == 1:
            teamraid_user = list(workers_still_alive.keys())[0]
            if len(list(workers_still_alive[teamraid_user].keys())) == 1:
                return workers_still_alive
        for teamraid_user, worker_data in workers_still_alive.items():
            for worker_type, worker_power in worker_data.items():
                worker_damage = round(100 * worker_power / next_enemy_power)
                hp_remaining = next_enemy_hp - worker_damage
                if hp_remaining <= 0:
                    if not recommended_worker:
                        recommended_worker[teamraid_user] = {}
                        recommended_worker[teamraid_user][worker_type] = worker_power
                        continue
                    recommended_worker_user = list(recommended_worker.keys())[0]
                    recommended_worker_type = list(recommended_worker[recommended_worker_user].keys())[0]
                    recommended_worker_power = recommended_worker[recommended_worker_user][recommended_worker_type]
                    if worker_power < recommended_worker_power:
                        recommended_worker = {}
                        recommended_worker[teamraid_user] = {}
                        recommended_worker[teamraid_user][worker_type] = worker_power
        if not recommended_worker:
            all_worker_powers = []
            for teamraid_user, worker_data in workers_still_alive.items():
                for worker_type, worker_power in worker_data.items():
                    worker_damage = round(100 * worker_power / next_enemy_power)
                    all_worker_powers.append((worker_power, worker_damage))
            best_combination = []
            for combination in combinations(all_worker_powers, 2):
                summed_damage = combination[0][1] + combination[1][1]
                if summed_damage >= next_enemy_hp:
                    if not best_combination:
                        best_combination = combination
                    elif summed_damage < best_combination[0][1] + best_combination[1][1]:
                        best_combination = combination
            for teamraid_user, worker_data in workers_still_alive.items():
                for worker_type, worker_power in worker_data.items():
                    for best_worker_power, best_worker_damage in best_combination:
                        if best_worker_power == worker_power:
                            recommended_worker[teamraid_user] = {}
                            recommended_worker[teamraid_user][worker_type] = worker_power
        if not recommended_worker:
            best_combination = []
            for combination in combinations(all_worker_powers, 3):
                summed_damage = combination[0][1] + combination[1][1] + combination[2][1]
                if summed_damage >= next_enemy_hp:
                    if not best_combination:
                        best_combination = combination
                    elif summed_damage < best_combination[0][1] + best_combination[1][1] + best_combination[2][1]:
                        best_combination = combination
            for teamraid_user, worker_data in workers_still_alive.items():
                for worker_type, worker_power in worker_data.items():
                    for best_worker_power, best_worker_damage in best_combination:
                        if best_worker_power == worker_power:
                            recommended_worker[teamraid_user] = {}
                            recommended_worker[teamraid_user][worker_type] = worker_power
        return recommended_worker

    add_reaction = False
    search_strings = [
        'farms will be raided in order', #English
    ]
    if (any(search_string in embed_data['footer']['text'].lower() for search_string in search_strings)
        and not 'raidpoints' in embed_data['field0']['name']):
        teamraid_users_workers = {}
        workers_incomplete = False
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
        if clan_settings is None:
            try:
                clan_settings: clans.Clan = await clans.get_clan_by_member_id(user.id)
            except exceptions.NoDataFoundError:
                return add_reaction
        if not clan_settings.helper_teamraid_enabled: return add_reaction

        def raid_message_check(payload: discord.RawMessageUpdateEvent):
            #return message_after.id == message.id
            try:
                author_name = payload.data['embeds'][0]['author']['name']
                return author_name == message.embeds[0].author.name and payload.data['embeds'][0]['fields'][0]['name'].count('farm') >= 4 # Temporary workaround for that weird issue
            except:
                return False

        enemy_name_match = re.search(r'\*\*(.+?) farms', embed_data['field0']['name'].lower())
        enemy_name = enemy_name_match.group(1).upper()
        embed = discord.Embed(color=settings.EMBED_COLOR)
        user_workers_power = {}
        for teamraid_user in teamraid_users:
            user_workers_required = {}
            user_workers_power[teamraid_user.name] = {}
            field_workers = ''
            try:
                user_settings: users.User = await users.get_user(teamraid_user.id)
                user_workers = await workers.get_user_workers(teamraid_user.id)
                for user_worker in user_workers:
                    if user_worker.worker_name in teamraid_users_workers[teamraid_user.name]:
                        user_workers_required[user_worker.worker_name] = user_worker.worker_level
            except (exceptions.FirstTimeUserError, exceptions.NoDataFoundError):
                user_settings = user_workers = None
            if user_settings is not None:
                try:
                    await functions.change_user_energy(user_settings, -40)
                    if user_settings.reactions_enabled: add_reaction = True
                except exceptions.EnergyFullTimeOutdatedError:
                    pass
                except exceptions.EnergyFullTimeNoneError:
                    pass
            for worker_type in teamraid_users_workers[teamraid_user.name]:
                worker_emoji = getattr(emojis, f'WORKER_{worker_type}_A'.upper(), emojis.WARNING)
                if user_workers is None or user_settings is None:
                    workers_incomplete = True
                    current_worker = f'{worker_emoji} `       ?`{emojis.WORKER_POWER}'
                elif not user_settings.bot_enabled:
                    workers_incomplete = True
                    current_worker = f'{worker_emoji} `       ?`{emojis.WORKER_POWER}'
                else:
                    worker_power = (
                        ((strings.WORKER_STATS[worker_type]['speed'] + strings.WORKER_STATS[worker_type]['strength']
                        + strings.WORKER_STATS[worker_type]['intelligence']))
                        * (1 + (strings.WORKER_STATS[worker_type]['tier']) / 2.5) * (1 + user_workers_required[worker_type] / 1.25)
                    )
                    user_workers_power[teamraid_user.name][worker_type] = worker_power
                    worker_power = round(worker_power, 2)
                    worker_power_str = f'{worker_power:,g}'.rjust(8)
                    current_worker = f'{worker_emoji} `{worker_power_str}`{emojis.WORKER_POWER}'
                field_workers = (
                    f'{field_workers}\n'
                    f'{current_worker}'
                )
            embed.add_field(
                name = teamraid_user.name,
                value = field_workers.strip()
            )
        enemies_power = await read_enemy_farms(message)
        logs.logger.info(
            f'--- Teamraid guide log ---\n'
            f'Enemy name: {enemy_name}\n'
            f'Enemy farms: {enemies_power}\n'
            f'Workers: {user_workers_power}'
        )
        field_enemies = ''
        for enemy_type, enemy_power_hp in enemies_power.items():
            enemy_power, enemy_hp = enemy_power_hp
            enemy_emoji = getattr(emojis, f'WORKER_{enemy_type[:-1]}_A'.upper(), emojis.WARNING)
            enemy_damage_required = round((enemy_hp-0.5) * enemy_power / 100,2)
            worker_power = 1
            field_enemies = (
                f'{field_enemies}\n'
                f'{enemy_emoji} - needs `{enemy_damage_required:,g}`{emojis.WORKER_POWER} to one-shot'
            )
            enemies_power.keys()
            if (list(enemies_power.keys()).index(enemy_type) + 1) % 3 == 0: field_enemies = f'{field_enemies}\n'
        if workers_incomplete:
            embed.insert_field_at(
                0,
                name = 'Next worker recommendation',
                value = '_I don\'t have the data of all teamraid users, sorry._',
                inline = False
            )
        else:
            next_enemy_power, next_enemy_hp = enemies_power[list(enemies_power.keys())[0]]
            workers_still_alive = copy.deepcopy(user_workers_power)
            recommended_worker = await get_recommended_worker((next_enemy_power, next_enemy_hp), workers_still_alive)
            if recommended_worker:
                recommended_worker_user = list(recommended_worker.keys())[0]
                recommended_worker_type = list(recommended_worker[recommended_worker_user].keys())[0]
                recommended_worker_emoji = getattr(emojis, f'WORKER_{recommended_worker_type}_A'.upper(), emojis.WARNING)
                recommended_worker_power = round(recommended_worker[recommended_worker_user][recommended_worker_type], 2)
                embed.insert_field_at(
                    0,
                    name = 'Next worker recommendation',
                    value = (
                        f'{recommended_worker_emoji} **{recommended_worker_user}** - '
                        f'**`{recommended_worker_power:,g}`**{emojis.WORKER_POWER}\n'
                        f'{emojis.BLANK}'
                    ),
                    inline = False
                )
                logs.logger.info(
                    f'--- Teamraid against {enemy_name} ---\n'
                    f'Enemies: {enemies_power}\n'
                    f'Workers left: {workers_still_alive}\n'
                    f'Recommendation: {recommended_worker}'
                )
            else:
                embed.insert_field_at(
                    0,
                    name = 'Next worker recommendation',
                    value = f'_No recommendation found, sorry._\n{emojis.BLANK}',
                    inline = False
                )
                logs.logger.info(
                    f'--- Teamraid against {enemy_name} ---\n'
                    f'Enemies: {enemies_power}\n'
                    f'Workers left: {workers_still_alive}\n'
                    f'Recommendation: None'
                )
        embed.insert_field_at(
            index=1,
            name = enemy_name,
            value = f'{field_enemies.strip()}\n{emojis.BLANK}',
            inline = False
        )
        embed.insert_field_at(
            index=2,
            name = clan_settings.clan_name.upper(),
            value = '_If a worker power shows as `?`, the player is not using Molly or has not shown me their workers list._',
            inline = False
        )
        message_helper = await message.reply(embed=embed)

        if not workers_incomplete:
            while True:
                try:
                    payload = await bot.wait_for('raw_message_edit', check=raid_message_check,
                                                 timeout=settings.INTERACTION_TIMEOUT)
                except TimeoutError:
                    embed.remove_field(0)
                    embed.insert_field_at(
                        0,
                        name = 'Next worker recommendation',
                        value = f'_Helper timed out._\n{emojis.BLANK}',
                        inline = False
                    )
                    await message_helper.edit(embed=embed)
                    break
                active_component = False
                if 'components' not in payload.data: continue
                message_components = payload.data['components']
                for row in message_components:
                    for component in row['components']:
                        disabled = component.get('disabled', False)
                        if disabled:
                            worker_name_match = re.search(r'^(.+?)worker', component['emoji']['name'].lower())
                            try:
                                del workers_still_alive[component['label']][worker_name_match.group(1)]
                                if not workers_still_alive[component['label']]: del workers_still_alive[component['label']]
                            except KeyError:
                                pass
                        else:
                            active_component = True

                embed.remove_field(0)
                embed.remove_field(0)
                if active_component:
                    enemies_power = await read_enemy_farms(payload)
                    field_enemies = ''
                    for enemy_type, enemy_power_hp in enemies_power.items():
                        enemy_power, enemy_hp = enemy_power_hp
                        enemy_emoji = getattr(emojis, f'WORKER_{enemy_type[:-1]}_A'.upper(), emojis.WARNING)
                        enemy_damage_required = round((enemy_hp-0.5) * enemy_power / 100,2)
                        worker_power = 1
                        if enemy_damage_required <= 0:
                            field_enemies = (
                                f'{field_enemies}\n'
                                f'{enemy_emoji} - _killed_'
                            )
                        else:
                            field_enemies = (
                                f'{field_enemies}\n'
                                f'{enemy_emoji} - needs `{enemy_damage_required:,g}`{emojis.WORKER_POWER} to one-shot'
                            )
                        if (list(enemies_power.keys()).index(enemy_type) + 1) % 3 == 0: field_enemies = f'{field_enemies}\n'
                    embed.insert_field_at(
                        index=0,
                        name = enemy_name,
                        value = f'{field_enemies.strip()}\n{emojis.BLANK}',
                        inline = False
                    )
                    for enemy_type, enemy_power_hp in enemies_power.copy().items():
                        if enemy_power_hp[1] == 0: del enemies_power[enemy_type]
                    next_enemy_power, next_enemy_hp = enemies_power[list(enemies_power.keys())[0]]
                    recommended_worker = await get_recommended_worker((next_enemy_power, next_enemy_hp), workers_still_alive)
                    if recommended_worker:
                        recommended_worker_user = list(recommended_worker.keys())[0]
                        recommended_worker_type = list(recommended_worker[recommended_worker_user].keys())[0]
                        recommended_worker_emoji = getattr(emojis, f'WORKER_{recommended_worker_type}_A'.upper(), emojis.WARNING)
                        recommended_worker_power = round(recommended_worker[recommended_worker_user][recommended_worker_type], 2)
                        embed.insert_field_at(
                            0,
                            name = 'Next worker recommendation',
                            value = (
                                f'{recommended_worker_emoji} **{recommended_worker_user}** - '
                                f'**{recommended_worker_power:,g}** {emojis.WORKER_POWER}\n'
                                f'{emojis.BLANK}'
                            ),
                            inline = False
                        )
                        logs.logger.info(
                            f'--- Teamraid against {enemy_name} ---\n'
                            f'Enemies: {enemies_power}\n'
                            f'Workers left: {workers_still_alive}\n'
                            f'Recommendation: {recommended_worker}'
                        )
                    else:
                        embed.insert_field_at(
                            0,
                            name = 'Next worker recommendation',
                            value = f'_No recommendation found, sorry._\n{emojis.BLANK}',
                            inline = False
                        )
                        logs.logger.info(
                            f'--- Teamraid against {enemy_name} ---\n'
                           f'Enemies: {enemies_power}\n'
                           f'Workers left: {workers_still_alive}\n'
                           f'Recommendation: None'
                        )
                if not active_component:
                    enemies_power = await read_enemy_farms(payload)
                    field_enemies = ''
                    enemy_count = 0
                    for enemy_type, enemy_power_hp in enemies_power.items():
                        enemy_power, enemy_hp = enemy_power_hp
                        enemy_emoji = getattr(emojis, f'WORKER_{enemy_type[:-1]}_A'.upper(), emojis.WARNING)
                        enemy_damage_required = round((enemy_hp-0.5) * enemy_power / 100,2)
                        worker_power = 1
                        if enemy_damage_required <= 0:
                            field_enemies = (
                                f'{field_enemies}\n'
                                f'{enemy_emoji} - _killed_'
                            )
                        else:
                            field_enemies = (
                                f'{field_enemies}\n'
                                f'{enemy_emoji} - needs `{enemy_damage_required:,g}`{emojis.WORKER_POWER} to one-shot'
                            )
                        enemy_count += 1    
                        if (list(enemies_power.keys()).index(enemy_type) + 1) % 3 == 0: field_enemies = f'{field_enemies}\n'
                    embed.insert_field_at(
                        index=0,
                        name = enemy_name,
                        value = f'{field_enemies.strip()}\n{emojis.BLANK}',
                        inline = False
                    )
                    embed.insert_field_at(
                        0,
                        name = 'Next worker recommendation',
                        value = f'_Teamraid completed._\n{emojis.BLANK}',
                        inline = False
                    )
                    logs.logger.info(
                        f'--- Teamraid against {enemy_name} ---\n'
                        f'Teamraid completed'
                    )
                try:
                    await message_helper.edit(embed=embed)
                except discord.NotFound:
                    return add_reaction
                if not active_component: break



async def create_clan_reminder(message: discord.Message, embed_data: Dict, clan_settings: Optional[clans.Clan]) -> bool:
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
    search_strings_teamraid = [
        '🔱',
        ':trident:',
    ]
    field_values = (
        f"{embed_data['field0']['value']}\n"
        f"{embed_data['field1']['value']}\n"
        f"{embed_data['field2']['value']}\n"
        f"{embed_data['field3']['value']}\n"
        f"{embed_data['field4']['value']}\n"
        f"{embed_data['field5']['value']}"
    )
    if (any(search_string in embed_data['description'].lower() for search_string in search_strings_description)
        and any(search_string in field_values.lower() for search_string in search_strings_teamraid)):
        if clan_settings is None:
            clan_name_match = None
            for line in field_values.split('\n'):
                clan_name_match = re.search(r"^\*\*(.+?)\*\*:", line)
                if clan_name_match: break
            try:
                clan_settings: clans.Clan = await clans.get_clan_by_clan_name(clan_name_match.group(1))
            except exceptions.NoDataFoundError:
                return add_reaction
        if not clan_settings.reminder_enabled: return add_reaction
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