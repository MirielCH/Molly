# payday.py

from datetime import timedelta
import re
from typing import Dict, Optional

import discord
from discord import utils

from cache import messages
from database import reminders, upgrades, users
from resources import emojis, exceptions, functions, regex, settings


UPGRADES_COST = {
    'farm slots': (0, 25, 200, 2_500, 16_000, 70_000, 400_000, 2_000_000),
    'energy regeneration': (0, 100, 800, 6_000, 35_000, 120_000, 900_000, 7_500_000),
    'worker efficiency': (0, 500, 2_500, 10_000, 80_000, 350_000, 2_000_000, 40_000_000),
    'max energy': (0, 1_000, 4_000, 30_000, 260_000, 900_000, 7_000_000, 50_000_000),
    'payday rewards': (0, 10_000, 50_000, 350_000, 3_000_000, 10_000_000, 90_000_000, 750_000_000),
    'payday keep': (0, 5_000, 25_000, 150_000, 1_000_000, 4_000_000, 25_000_000, 120_000_000),
    'teamfarm life': (0, 5_000, 1_000_000, 1_000_000_000),
    'farm bundle': (0, 1, 10, 1_000),
    'quality of life': (0, 10_000, 100_000),
    'roll luck': (0, 1_000, 4_000, 20_000, 80_000, 320_000, 1_280_000, 5_120_000, 20_480_000, 81_920_000, 327_680_000, 1_310_720_000, 5_242_880_000),
    'activity discount': (0, 3_500, 15_000, 80_000, 475_000, 2_000_000, 9_876_543, 50_000_000, 350_000_000, 2_000_000_000, 10_000_000_000),
}

UPGRADES_BONUSES = {
    'farm slots': (0, 2, 4, 5, 6, 7, 8, 9),
    'energy regeneration': ('0%', '30%', '50%', '70%', '85%', '100%', '110%', '120%'),
    'worker efficiency': ('0%', '10%', '15%', '20%', '22.5%', '25%', '27.5%', '30%'),
    'max energy': ('0%', '60%', '110%', '150%', '180%', '200%', '210%', '215%'), # Everything after 180 is assumptions
    'payday rewards': ('0%', '20%', '30%', '35%', '40%', '45%', '47.5%', '50%'),
    'payday keep': ('0%', '0.01%', '0.1%', '0.5%', '1%', '1.5%', '2%', '2.5%'),
    'teamfarm life': (0, 5, 10, 15),
    'farm bundle': (0, 1, 2, 3, 4),
    'quality of life': (0, 1, 2),
    'roll luck': (0, 0.25, 0.5, 0.75, 1, 1.2, 1.4, 1.6, 1.8, 2, 2.1, 2.2, 2.3),
    'activity discount': ('x0', 'x1', 'x2', 'x2.5', 'x3', 'x3.5', 'x4', 'x4.25', 'x4.5', 'x4.75', 'x5'),
}


async def process_message(bot: discord.Bot, message: discord.Message, embed_data: Dict, user: Optional[discord.User],
                          user_settings: Optional[users.User]) -> bool:
    """Processes the message for all /shop buy related actions.

    Returns
    -------
    - True if a logo reaction should be added to the message
    - False otherwise
    """
    return_values = []
    return_values.append(await call_upgrades_helper(message, embed_data, user, user_settings))
    return_values.append(await update_idlucks_and_raid_shield_on_payday(message, embed_data, user, user_settings))
    return any(return_values)


async def call_upgrades_helper(message: discord.Message, embed_data: Dict, user: Optional[discord.User],
                              user_settings: Optional[users.User]) -> bool:
    """Call the context helper when preparing for payday

    Returns
    -------
    - True if a logo reaction should be added to the message
    - False otherwise
    """
    add_reaction = False
    search_strings = [
        '— payday', #All languages
    ]
    search_strings_excluded = [
        'need to progress more', #All languages
    ]
    if (any(search_string in embed_data['author']['name'].lower() for search_string in search_strings)
        and all(search_string not in embed_data['description'].lower() for search_string in search_strings_excluded)):
        if user is None:
            if embed_data['embed_user'] is not None:
                user = embed_data['embed_user']
                user_settings = embed_data['embed_user_settings']
            else:
                user_name_match = re.search(regex.USERNAME_FROM_EMBED_AUTHOR, embed_data['author']['name'])
                user_name = user_name_match.group(1)
                user_command_message = (
                    await messages.find_message(message.channel.id, regex.COMMAND_PAYDAY, user_name=user_name)
                )
                user = user_command_message.author
        if user_settings is None:
            try:
                user_settings: users.User = await users.get_user(user.id)
            except exceptions.FirstTimeUserError:
                return add_reaction
        if not user_settings.bot_enabled or not user_settings.helper_upgrades_enabled: return add_reaction
        idlucks_match = re.search(r'^• ([0-9,]+?) <', embed_data['field1']['value'].lower())
        idlucks = int(re.sub(r'\D','', idlucks_match.group(1)))
        idlucks_after_payday = user_settings.idlucks + idlucks
        description = (
            f'_If you payday now, you will have **{idlucks_after_payday:,}** {emojis.IDLUCKS} idlucks._\n'
        )
        embed = discord.Embed(
            color = settings.EMBED_COLOR,
            title = f'Affordable {await functions.get_game_command(user_settings, "upgrades")}',
        )
        try:
            user_upgrades = await upgrades.get_all_upgrades(user.id)
        except exceptions.NoDataFoundError:
            description = (
                f'I can\'t list your next upgrades because I don\'t know them.\n'
                f'Please use {await functions.get_game_command(user_settings, "upgrades")} to update them first.'
            )
            return
        for upgrade in user_upgrades:
            if upgrade.name == 'farm bundle': continue
            if not upgrade.name in UPGRADES_COST or not upgrade.name in UPGRADES_BONUSES: continue
            try:
                upgrade_cost = UPGRADES_COST[upgrade.name][upgrade.level + 1]
                upgrade_bonus_current = UPGRADES_BONUSES[upgrade.name][upgrade.level]
                upgrade_bonus_next = UPGRADES_BONUSES[upgrade.name][upgrade.level + 1]
                emoji_affordable = emojis.ENABLED if user_settings.idlucks + idlucks >= upgrade_cost else emojis.DISABLED
            except IndexError:
                continue
            description = (
                f'{description}\n'
                f'{emoji_affordable} **{upgrade.name}**: `{upgrade_cost:,}` {emojis.IDLUCKS}\n'
                f'{emojis.BLANK} `+{upgrade_bonus_current}` ➜ `+{upgrade_bonus_next}` (level {upgrade.level + 1})'
            )
        if description == '': return
        embed.description = description
        await message.reply(embed=embed)
    return add_reaction


async def update_idlucks_and_raid_shield_on_payday(message: discord.Message, embed_data: Dict, user: Optional[discord.User],
                                                   user_settings: Optional[users.User]) -> bool:
    """Update the idluck amount and create boost reminder after paydaying.
    Also resets claim time if a claim reminder is active.

    Returns
    -------
    - True if a logo reaction should be added to the message
    - False otherwise
    """
    add_reaction = False
    search_strings = [
        'it\'s payday!', #English
    ]
    if any(search_string in embed_data['description'].lower() for search_string in search_strings):
        if user is None:
            user_command_message = (
                await messages.find_message(message.channel.id, regex.COMMAND_PAYDAY)
            )
            user = user_command_message.author
        try:
            user_settings: users.User = await users.get_user(user.id)
        except exceptions.FirstTimeUserError:
            return add_reaction
        if not user_settings.bot_enabled: return add_reaction
        idlucks_match = re.search(r'got ([0-9,]+?) <', embed_data['description'].lower())
        idlucks = int(re.sub(r'\D','', idlucks_match.group(1)))
        await user_settings.update(idlucks=idlucks)
        if user_settings.reminder_boosts.enabled:
            user_command = await functions.get_game_command(user_settings, 'boosts')
            boost_emoji = emojis.BOOSTS_EMOJIS.get('payday', '')
            reminder_message = (
                user_settings.reminder_boosts.message
                .replace('{boost_emoji}', boost_emoji)
                .replace('{boost_name}', 'payday')
                .replace('{command}', user_command)
                .replace('  ', ' ')
            )
            reminder: reminders.Reminder = (
                await reminders.insert_user_reminder(user.id, f'boost-payday', timedelta(minutes=30),
                                                     message.channel.id, reminder_message)
            )
        try:
            reminder: reminders.Reminder = await reminders.get_user_reminder(user.id, 'claim')
            current_time = utils.utcnow()
            await user_settings.update(last_claim_time=current_time)
            await reminder.update(end_time=current_time + timedelta(hours=user_settings.reminder_claim_last_selection))
        except exceptions.NoDataFoundError:
            pass
        if user_settings.reactions_enabled: add_reaction = True
    return add_reaction