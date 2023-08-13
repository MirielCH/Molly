# profile.py

from datetime import timedelta
import re
from typing import Dict, Optional

import discord
from discord import utils
from humanfriendly import format_timespan

from cache import messages
from database import upgrades, users
from resources import emojis, exceptions, regex, settings, strings


async def process_message(bot: discord.Bot, message: discord.Message, embed_data: Dict, user: Optional[discord.User],
                          user_settings: Optional[users.User]) -> bool:
    """Processes the message for all profile related actions.

    Returns
    -------
    - True if a logo reaction should be added to the message
    - False otherwise
    """
    return_values = []
    return_values.append(await call_energy_helper_and_update_idlucks(message, embed_data, user, user_settings))
    return any(return_values)


async def call_energy_helper_and_update_idlucks(message: discord.Message, embed_data: Dict,
                                                interaction_user: Optional[discord.User],
                                                user_settings: Optional[users.User]) -> bool:
    """• Update idluck count in the database
    • Show energy helper

    Returns
    -------
    - True if a logo reaction should be added to the message
    - False otherwise
    """
    add_reaction = False
    search_strings = [
        '— profile', #English
    ]
    if any(search_string in embed_data['author']['name'].lower() for search_string in search_strings):
        if interaction_user is None:
            user_name_match = re.search(regex.USERNAME_FROM_EMBED_AUTHOR, embed_data['author']['name'])
            user_name = user_name_match.group(1)
            user_command_message = (
                await messages.find_message(message.channel.id, regex.COMMAND_PROFILE, user_name=user_name)
            )
            if user_command_message is None: return add_reaction
            interaction_user = user_command_message.author
        if embed_data['embed_user'] != interaction_user: return add_reaction
        if user_settings is None:
            try:
                user_settings: users.User = await users.get_user(interaction_user.id)
            except exceptions.FirstTimeUserError:
                return add_reaction
        if not user_settings.bot_enabled: return add_reaction
        if user_settings.helper_upgrades_enabled:
            idlucks_match = re.search(r'idlucks\*\*: ([0-9,]+?)\n', embed_data['field3']['value'].lower())
            idlucks = int(re.sub('\D','', idlucks_match.group(1)))
            await user_settings.update(idlucks=idlucks)
        if user_settings.helper_energy_enabled:
            try:
                energy_upgrade: upgrades.Upgrade = await upgrades.get_upgrade(interaction_user.id, 'energy regeneration')
                multiplier_upgrade = strings.ENERGY_UPGRADE_LEVEL_MULTIPLIERS[energy_upgrade.level]
            except exceptions.NoDataFoundError:
                multiplier_upgrade = 1
            multiplier_donor = list(strings.DONOR_TIER_ENERGY_MULTIPLIERS.values())[user_settings.donor_tier]
            energy_match = re.search(r'1084593332312887396> (\d+)/(\d+)\n', embed_data['field0']['value'])
            energy_current, energy_max = energy_match.groups()
            energy_regen = 6 / (multiplier_donor * multiplier_upgrade)
            energy_regen_time = timedelta(minutes=energy_regen)
            if energy_regen_time.microseconds > 0:
                energy_regen_time = energy_regen_time + timedelta(microseconds=1_000_000 - energy_regen_time.microseconds)
            minutes_until_max = (int(energy_max) - int(energy_current)) * energy_regen
            full_time = utils.utcnow() + timedelta(minutes=minutes_until_max)
            full_info = f'**NOW**{emojis.WARNING}' if energy_current == energy_max else f'{utils.format_dt(full_time, "R")} when idling'
            embed = discord.Embed(
                color=settings.EMBED_COLOR,
                title = 'Energy stats',
                description =  (
                    f'{emojis.BP} **Regeneration**: Every {format_timespan(energy_regen_time)}\n'
                    f'{emojis.BP} **Energy limit**: Full {full_info}'
                )
            )
            percentage_donor = int((multiplier_donor - 1) * 100)
            percentage_upgrade = int((multiplier_upgrade - 1) * 100)
            embed.set_footer(text=f'Donor: +{percentage_donor}% | Upgrades: +{percentage_upgrade}%')
            await message.reply(embed=embed)
    return add_reaction