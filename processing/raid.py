# raid.py

import copy
from decimal import Decimal, ROUND_HALF_UP
import itertools
import re
from typing import Dict, Optional, Tuple

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
    async def calculate_best_solution(workers_power: Dict[str, int], enemies_power: Dict[str, int]) -> Tuple[int, Dict[str, int]]:
            """Calculates the best solution for a raid and returns a dictionary with the worker names and their power.
            The calculation returns the first solution that kills all enemies as there is no point in checking other
            solutions after that.

            Arguments
            ---------
            workers_power: Dict[worker_name: worker_power]
            enemies_power: Dict[enemy_name: enemy_power_remaining]

            Returns
            -------
            Tuple with the amount of killed enemies (int) and the solution (Dict[worker_name: worker_power])

            """
            workers_by_power = dict(sorted(workers_power.items(), key=lambda x:x[1]))
            remaining_workers = copy.deepcopy(workers_by_power)
            worker_solution = {}
            used_workers = {}
            possible_solutions = []
            killed_enemies = 0
            for enemy_name, enemy_power in enemies_power.items():
                worker_found = False
                for worker_name, power in remaining_workers.copy().items():
                    if power >= enemy_power:
                        used_workers[worker_name] = power
                        del remaining_workers[worker_name]
                        worker_found = True
                        killed_enemies += 1
                        break
                if worker_found: continue
                permutations = list(itertools.permutations(list(remaining_workers.keys())))
                possible_solutions = []
                for permutation in permutations:
                    possible_solutions.append(list(used_workers.keys()) + list(permutation))
                break
            if possible_solutions:    
                best_solution = []
                for possible_solution in possible_solutions:
                    enemies_powers_copy = copy.deepcopy(enemies_power)
                    for worker_name in possible_solution:    
                        for enemy_name, enemy_power in enemies_powers_copy.items():
                            if enemy_power == 0: continue
                            worker_power = workers_by_power[worker_name]
                            power_remaining = enemies_powers_copy[enemy_name] - worker_power
                            used_workers[worker_name] = worker_power
                            if power_remaining < 0: power_remaining = 0
                            enemies_powers_copy[enemy_name] = power_remaining
                            break
                        killed_enemies = len([enemy_name for enemy_name, enemy_power in enemies_powers_copy.items() if enemy_power == 0])
                        if killed_enemies >= len(enemies_powers_copy.keys()): break
                    if best_solution:
                        if killed_enemies > best_solution[0]:
                            best_solution = [killed_enemies, possible_solution]
                    else:
                        best_solution = [killed_enemies, possible_solution]
                    if killed_enemies >= len(enemies_power.keys()): break
                killed_enemies = best_solution[0]
            for x in range(empty_fields_found):
                if len(used_workers) < len(workers_power):
                    for worker_name, worker_power in workers_power.items():
                        if worker_name not in used_workers:
                            used_workers[worker_name] = worker_power
                            break
                    
                #worker_solution = {worker_name: workers_by_power[worker_name] for worker_name in best_solution[1]}
            return (killed_enemies, used_workers)
    
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
        enemies_stats = {}
        field_enemies = ''
        empty_fields_found = 0
        for line in embed_data['field0']['value'].split('\n'):
            if 'none' in line.lower():
                 enemy_emoji = emojis.NONE
                 enemy_power = 0
                 empty_fields_found += 1
            else:
                enemy_data_match = re.search(r'<a:(.+?)worker.+lv(\d+) \|.+`(\d+)/(\d+)`', line.lower())
                enemy_type = enemy_data_match.group(1)
                enemy_level = int(re.sub('\D','',enemy_data_match.group(2)))
                enemy_hp_current = int(enemy_data_match.group(3))
                enemy_hp_max = int(enemy_data_match.group(4))
                enemy_power = (
                    (strings.WORKER_STATS[enemy_type]['speed'] + strings.WORKER_STATS[enemy_type]['strength'] + strings.WORKER_STATS[enemy_type]['intelligence'])
                    * (1 + (strings.WORKER_TYPES.index(enemy_type) + 1) / 4) * (1 + enemy_level / 2.5) * (enemy_hp_max / 100)
                )
                enemy_power = int(Decimal(enemy_power).quantize(Decimal(1), rounding=ROUND_HALF_UP))
                enemies_stats[enemy_type] = {
                    'level': enemy_level,
                    'power': enemy_power,
                    'power_remaining': enemy_power,
                    'hp_max': enemy_hp_max
                }
                enemy_emoji = getattr(emojis, f'WORKER_{enemy_type}_A'.upper(), emojis.WARNING)
            field_enemies = (
                f'{field_enemies}\n'
                f'{enemy_emoji} - **{enemy_power}** {emojis.WORKER_POWER}'
            )
        user_workers = await workers.get_user_workers(user.id)
        field_workers = ''
        workers_power = {}
        for worker_type in strings.WORKER_TYPES:
            worker = None
            for user_worker in user_workers:
                if user_worker.worker_name == worker_type:
                    worker = user_worker
                    break
            if worker is None: continue
            worker_power = round(
                ((strings.WORKER_STATS[worker.worker_name]['speed'] + strings.WORKER_STATS[worker.worker_name]['strength']
                  + strings.WORKER_STATS[worker.worker_name]['intelligence']))
                * (1 + (strings.WORKER_TYPES.index(worker.worker_name) + 1) / 4) * (1 + worker.worker_level / 2.5)
            )
            workers_power[worker.worker_name] = worker_power
            worker_emoji = getattr(emojis, f'WORKER_{worker.worker_name}_A'.upper(), emojis.WARNING)
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
            name = 'Enemy farms',
            value = field_enemies.strip()
        )
        enemies_power = {enemy_name: enemy_stats['power'] for enemy_name, enemy_stats in enemies_stats.items()}
        killed_enemies, worker_solution = await calculate_best_solution(workers_power, enemies_power)
        worker_emojis = {}
        for worker_name, power in worker_solution.items():
            worker_emojis[worker_name] = getattr(emojis, f'WORKER_{worker_name}_S'.upper(), emojis.WARNING)
        killed_enemies = 'all' if killed_enemies >= len(enemies_power.keys()) else killed_enemies
        field_solution = ''
        for worker_name, emoji in worker_emojis.items():
            field_solution = emoji if field_solution == '' else f'{field_solution} ➜ {emoji}'
        embed.insert_field_at(
            0,
            name = 'Solution',
            value = f'{field_solution.strip()}\n{emojis.BLANK}',
            inline = False
        )
        embed.set_footer(text=f'You can kill {killed_enemies} enemies')


        # Wait for edits. Get last used  If correct choice was taken, cross out worker, move on with current solution.
        # If not, recalculate and present new solution
            
        
                    
        

        
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