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
from resources import emojis, exceptions, functions, logs, regex, settings, strings


async def process_message(bot: discord.Bot, message: discord.Message, embed_data: Dict, user: Optional[discord.User],
                          user_settings: Optional[users.User]) -> bool:
    """Processes the message for all raid related actions.

    Returns
    -------
    - True if a logo reaction should be added to the message
    - False otherwise
    """
    return_values = []
    return_values.append(await call_raid_helper(bot, message, embed_data, user, user_settings))
    return_values.append(await track_raid(message, embed_data, user, user_settings))
    return any(return_values)


async def call_raid_helper(bot: discord.Bot, message: discord.Message, embed_data: Dict, user: Optional[discord.User],
                           user_settings: Optional[users.User]) -> bool:
    """Calls the raid helper

    Returns
    -------
    - True if a logo reaction should be added to the message
    - False otherwise
    """
    async def read_enemy_farms(message: discord.Message) -> Tuple[int, Dict[str, int]]:
        """Returns the name and power of the enemy farms found in field 0. Also returns the amount of empty farms.

        Arguments
        ---------
        message: The message with the farms in field 0

        Returns
        -------
        Tuple with the amount of empty farms (int) and the enemies (Dict[enemy_name: enemy_power])
        """
        enemies_power = {}
        empty_farms_found = 0
        for line in message.embeds[0].fields[0].value.split('\n'):
            if 'none' in line.lower():
                 empty_farms_found += 1
            else:
                enemy_data_match = re.search(r'<a:(.+?)worker.+lv(\d+) \|.+`(\d+)/(\d+)`', line.lower())
                enemy_name = enemy_data_match.group(1)
                enemy_level = int(re.sub('\D','',enemy_data_match.group(2)))
                enemy_hp_current = int(enemy_data_match.group(3))
                enemy_hp_max = int(enemy_data_match.group(4))
                enemy_power = (
                    (strings.WORKER_STATS[enemy_name]['speed'] + strings.WORKER_STATS[enemy_name]['strength']
                     + strings.WORKER_STATS[enemy_name]['intelligence'])
                    * (1 + (strings.WORKER_TYPES.index(enemy_name) + 1) / 4)
                    * (1 + enemy_level / 2.5) * (enemy_hp_max / 100) / enemy_hp_max * enemy_hp_current
                )
                if (enemy_power - 0.5).is_integer():
                    logs.logger.info(f'Worker {enemy_name} at level {enemy_level} has a power of {enemy_power}')
                enemy_power = int(Decimal(enemy_power).quantize(Decimal(1), rounding=ROUND_HALF_UP))
                enemies_power[enemy_name] = enemy_power
        return (empty_farms_found, enemies_power)

    async def calculate_best_solution(workers_power: Dict[str, int], enemies_power: Dict[str, int], empty_farms_found: int) -> Tuple[int, Dict[str, int]]:
            """Calculates the best solution for a raid and returns a dictionary with the worker names and their power.
            The calculation returns the first solution that kills all enemies as there is no point in checking other
            solutions after that.

            Arguments
            ---------
            workers_power: Dict[worker_name: worker_power]
            enemies_power: Dict[enemy_name: enemy_power_remaining]
            empty_farms_found: int

            Returns
            -------
            Tuple with the amount of killed enemies (int) and the solution (Dict[worker_name: worker_power])

            """
            workers_by_power = dict(sorted(workers_power.items(), key=lambda x:x[1]))
            remaining_workers = copy.deepcopy(workers_by_power)
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
            for x in range(empty_farms_found):
                if len(used_workers) < len(workers_power):
                    for worker_name, worker_power in workers_power.items():
                        if worker_name not in used_workers:
                            used_workers[worker_name] = worker_power
                            break
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

        def raid_message_check(message_before: discord.Message, message_after: discord.Message):
            return message_after.id == message.id
        embed = discord.Embed()
        msg_error_workers_outdated = (
                f'Sorry, I can\'t provide any guidance because I don\'t know all of your workers. Please use '
                f'{await functions.get_game_command(user_settings, "worker stats")} to update them before your next '
                f'raid.'
            )
        try:
            user_workers = await workers.get_user_workers(user.id)
        except exceptions.NoDataFoundError:
            await message.reply(msg_error_workers_outdated)
            return add_reaction
        worker_levels = {user_worker.worker_name: user_worker.worker_level for user_worker in user_workers}
        worker_levels_sorted = {}
        for worker_type in strings.WORKER_TYPES:
            if worker_type in worker_levels:
                worker_levels_sorted[worker_type] = worker_levels[worker_type]
        for row in message.components:
            for button in row.children:
                worker_name_match = re.search(r'^(.+?)worker', button.emoji.name.lower())
                if worker_name_match.group(1) not in worker_levels_sorted:
                    await message.reply(msg_error_workers_outdated)
                    return add_reaction
        field_workers = ''
        workers_power = {}
        for worker_name, worker_level in worker_levels_sorted.items():
            worker_power = round(
                ((strings.WORKER_STATS[worker_name]['speed'] + strings.WORKER_STATS[worker_name]['strength']
                  + strings.WORKER_STATS[worker_name]['intelligence']))
                * (1 + (strings.WORKER_TYPES.index(worker_name) + 1) / 4) * (1 + worker_level / 2.5)
            )
            workers_power[worker_name] = worker_power
            if not user_settings.helper_raid_compact_mode_enabled:
                worker_emoji = getattr(emojis, f'WORKER_{worker_name}_A'.upper(), emojis.WARNING)
                field_workers = (
                    f'{field_workers}\n'
                    f'{worker_emoji} - **{worker_power}** {emojis.WORKER_POWER}'
                )
        if not user_settings.helper_raid_compact_mode_enabled:
            embed.add_field(
                name = 'Your workers',
                value = field_workers.strip()
            )   
        empty_farms_found, enemies_power = await read_enemy_farms(message)
        if not user_settings.helper_raid_compact_mode_enabled:
            field_enemies = ''
            for enemy_name, enemy_power in enemies_power.items():
                enemy_emoji = getattr(emojis, f'WORKER_{enemy_name}_A'.upper(), emojis.WARNING)
                field_enemies = (
                    f'{field_enemies}\n'
                    f'{enemy_emoji} - **{enemy_power}** {emojis.WORKER_POWER}'
                )
            embed.add_field(
                name = 'Enemy farms',
                value = field_enemies.strip()
            )
        killed_enemies, worker_solution = await calculate_best_solution(workers_power, enemies_power, empty_farms_found)
        worker_emojis = {}
        for worker_name, power in worker_solution.items():
            worker_emojis[worker_name] = getattr(emojis, f'WORKER_{worker_name}_S'.upper(), emojis.WARNING)
        killed_enemies = 'all' if killed_enemies >= len(enemies_power.keys()) else killed_enemies
        field_solution = ''
        for worker_name, emoji in worker_emojis.items():
            field_solution = emoji if field_solution == '' else f'{field_solution} ➜ {emoji}'
        worker_solution_remaining = list(worker_solution.keys())
        embed.insert_field_at(
            0,
            name = 'Raid guide',
            value = f'{field_solution.strip()}\n{emojis.BLANK}',
            inline = False
        )
        embed.set_footer(text=f'You can kill {killed_enemies} enemies')
        message_helper = await message.reply(embed=embed)

        while True:
            try:
                _, updated_message = await bot.wait_for('message_edit', check=raid_message_check,
                                                     timeout=settings.INTERACTION_TIMEOUT)
            except TimeoutError:
                embed.remove_field(0)
                embed.insert_field_at(
                    0,
                    name = 'Raid guide',
                    value = '_Timed out._',
                    inline = False
                )
                await message_helper.edit(embed=embed)
                break
            active_component = False
            disabled_workers = []
            for row in updated_message.components:
                for button in row.children:
                    if button.disabled:
                        worker_name_match = re.search(r'^(.+?)worker', button.emoji.name.lower())
                        disabled_workers.append(worker_name_match.group(1))
                    else:
                        active_component = True
            solution_still_valid = True
            workers_still_alive = list(workers_power.keys())
            embed.remove_field(0)
            if active_component:
                for worker_name in disabled_workers:
                    if worker_name in workers_still_alive: workers_still_alive.remove(worker_name)
                    worker_emojis[worker_name] = getattr(emojis, f'WORKER_{worker_name}_DEAD'.upper(), emojis.WARNING)
                    if (worker_name in worker_solution_remaining and worker_name != worker_solution_remaining[0]) or worker_name not in worker_solution:
                        solution_still_valid = False
                if not solution_still_valid:
                    workers_power = {worker_name: worker_power for worker_name, worker_power in workers_power.items() if worker_name in workers_still_alive}
                    empty_farms_found, enemies_power = await read_enemy_farms(message)
                    killed_enemies, worker_solution = await calculate_best_solution(workers_power, enemies_power, empty_farms_found)
                    worker_solution_remaining = list(worker_solution.keys())
                    for worker_name, worker_emoji in worker_emojis.copy().items():
                        if not '_x' in worker_emoji: del worker_emojis[worker_name]
                    for worker_name, power in worker_solution.items():
                        worker_emojis[worker_name] = getattr(emojis, f'WORKER_{worker_name}_S'.upper(), emojis.WARNING)
                    killed_enemies = 'all' if killed_enemies >= len(enemies_power.keys()) else killed_enemies
                else:
                    if worker_solution_remaining: del worker_solution_remaining[0]
                field_solution = ''
                for worker_name, emoji in worker_emojis.items():
                    field_solution = emoji if field_solution == '' else f'{field_solution} ➜ {emoji}'
                embed.insert_field_at(
                    0,
                    name = 'Raid guide',
                    value = f'{field_solution.strip()}\n{emojis.BLANK}',
                    inline = False
                )
                embed.set_footer(text=f'You can kill {killed_enemies} enemies')
            if not active_component:
                embed.insert_field_at(
                    0,
                    name = 'Raid guide',
                    value = '_Raid completed._',
                    inline = False
                )
            await message_helper.edit(embed=embed)
            if not active_component: break


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
        '🔱',
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