# upgrades.py

import re
from typing import Dict, Optional

import discord

from cache import messages
from database import upgrades, users
from resources import exceptions, regex


async def process_message(bot: discord.Bot, message: discord.Message, embed_data: Dict, user: Optional[discord.User],
                          user_settings: Optional[users.User]) -> bool:
    """Processes the message for all /use related actions.

    Returns
    -------
    - True if a logo reaction should be added to the message
    - False otherwise
    """
    return_values = []
    return_values.append(await track_upgrades_overview(message, embed_data, user, user_settings))
    return_values.append(await track_upgrade(message, user))
    return any(return_values)


async def track_upgrades_overview(message: discord.Message, embed_data: Dict, user: Optional[discord.User],
                                  user_settings: Optional[users.User]) -> bool:
    """Tacks upgrades from the upgrades overview embed

    Returns
    -------
    - True if a logo reaction should be added to the message
    - False otherwise
    """
    add_reaction = False
    search_strings = [
        'buy an upgrade with `', #English
    ]
    if any(search_string in embed_data['description'].lower() for search_string in search_strings):
        if user is None:
            user_command_message = (
                await messages.find_message(message.channel.id, regex.COMMAND_UPGRADES_OVERVIEW)
            )
            user = user_command_message.author
        try:
            user_settings: users.User = await users.get_user(user.id)
        except exceptions.FirstTimeUserError:
            return add_reaction
        if not user_settings.bot_enabled or not user_settings.helper_context_enabled: return add_reaction
        for field in message.embeds[0].fields:
            data_match = re.search(r'^`(\d+)`.+__\*\*(.+?)\*\*.+level\*\*:\s(\d+)\s\|', field.value.lower(), re.DOTALL)
            sort_index = int(data_match.group(1))
            name = data_match.group(2)
            level = int(data_match.group(3))
            try:
                upgrade: upgrades.Upgrade = await upgrades.get_upgrade(user.id, name)
                await upgrade.update(sort_index=sort_index, level=level)
            except exceptions.NoDataFoundError:
                await upgrades.insert_upgrade(user.id, name, level, sort_index)
        if user_settings.reactions_enabled: add_reaction = True
    return add_reaction


async def track_upgrade(message: discord.Message, user: Optional[discord.User]) -> bool:
    """Tacks upgrades from the upgrade message

    Returns
    -------
    - True if a logo reaction should be added to the message
    - False otherwise
    """
    add_reaction = False
    search_strings = [
        '` upgraded to level ', #English
    ]
    if any(search_string in message.content.lower() for search_string in search_strings):
        if user is None:
            user = message.mentions[0]
        try:
            user_settings: users.User = await users.get_user(user.id)
        except exceptions.FirstTimeUserError:
            return add_reaction
        if not user_settings.bot_enabled or not user_settings.helper_context_enabled: return add_reaction
        name_level_match = re.search(r'\d+> `(.+?)` .+level\s(\d+)\s', message.content.lower())
        name = name_level_match.group(1)
        level = int(name_level_match.group(2))
        try:
            upgrade: upgrades.Upgrade = await upgrades.get_upgrade(user.id, name)
            await upgrade.update(level=level)
        except exceptions.NoDataFoundError:
            return
        if user_settings.reactions_enabled: add_reaction = True
    return add_reaction