# donate.py

import re
from typing import Dict, Optional

import discord

from cache import messages
from database import users
from resources import exceptions, regex, strings


async def process_message(bot: discord.Bot, message: discord.Message, embed_data: Dict, user: Optional[discord.User],
                          user_settings: Optional[users.User]) -> bool:
    """Processes the message for all donate related actions.

    Returns
    -------
    - True if a logo reaction should be added to the message
    - False otherwise
    """
    return_values = []
    return_values.append(await update_donor_tier(message, embed_data, user, user_settings))
    return any(return_values)


async def update_donor_tier(message: discord.Message, embed_data: Dict, user: Optional[discord.User],
                                                user_settings: Optional[users.User]) -> bool:
    """Update donor tier in the database

    Returns
    -------
    - True if a logo reaction should be added to the message
    - False otherwise
    """
    add_reaction = False
    search_strings = [
        'if you want to support', #English
    ]
    if any(search_string in embed_data['description'].lower() for search_string in search_strings):
        if user is None:
            user_command_message = (
                await messages.find_message(message.channel.id, regex.COMMAND_DONATE)
            )
            if user_command_message is None: return add_reaction
            user = user_command_message.author
        if user_settings is None:
            try:
                user_settings: users.User = await users.get_user(user.id)
            except exceptions.FirstTimeUserError:
                return add_reaction
        if not user_settings.bot_enabled: return add_reaction
        if embed_data['field0']['name'] == '':
            donor_tier = 0
        else:
            donor_tier_match = re.search(r'| (.+?) donator	', embed_data['field0']['name'].lower())
            donor_tier = list(strings.DONOR_TIER_ENERGY_MULTIPLIERS.keys()).index(donor_tier_match.group(1).lower())
        await user_settings.update(donor_tier=donor_tier)
        add_reaction = True
    return add_reaction