# payday.py

import re
from typing import Dict, Optional

import discord

from cache import messages
from database import upgrades, users
from resources import emojis, exceptions, functions, regex, settings


UPGRADES_COST = {
    'farm slots': (0, 25, 200, 2_500, 16_000, 70_000, 400_000, 2_000_000),
    'energy regeneration': (0, 100, 800, 6_000, 35_000, 120_000, 900_000, 7_500_000),
    'worker efficiency': (0, 500, 2_500, 10_000, 80_000, 350_000, 2_000_000, 40_000_000),
    'max energy': (0, 1_000, 4_000, 30_000, 260_000, 900_000, 7_000_000, 50_000_000),
    'payday rewards': (0, 10_000, 50_000, 350_000, 3_000_000, 10_000_000, 90_000_000, 750_000_000),
    'payday keep': (0, 5_000, 25_000, 150_000, 1_000_000, 4_000_000, 25_000_000, 120_000_000),
    'farm life': (0, 5_000, 1_000_000, 1_000_000_000),
    'farm bundle': (0, 1, 10, 1_000),
    'quality of life': (0, 10_000, 100_000),
}

UPGRADES_BONUSES = {
    'farm slots': (0, 2, 4, 5, 6, 7, 8, 9),
    'energy regeneration': ('0%', '20%', '35%', '50%', '60%', '70%', '75%', '80%'),
    'worker efficiency': ('0%', '10%', '15%', '20%', '22.5%', '25%', '27.5%', '30%'),
    'max energy': ('0%', '50%', '90%', '120%', '150%', '170%', '190%', '200%'),
    'payday rewards': ('0%', '20%', '30%', '35%', '40%', '45%', '47.5%', '50%'),
    'payday keep': ('0%', '0.01%', '0.1%', '0.5%', '1%', '1.5%', '2%', '2.5%'),
    'farm life': (0, 5, 10, 15),
    'farm bundle': (0, 1, 2, 3, 4),
    'quality of life': (0, 1, 2),
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
    return_values.append(await update_idlucks(message, embed_data, user, user_settings))
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
    if any(search_string in embed_data['author']['name'].lower() for search_string in search_strings):
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


async def update_idlucks(message: discord.Message, embed_data: Dict, user: Optional[discord.User],
                              user_settings: Optional[users.User]) -> bool:
    """Update the idluck amount after paydaying

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
        if user_settings.reactions_enabled: add_reaction = True
    return add_reaction