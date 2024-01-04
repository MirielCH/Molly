# inventory.py

import re
from typing import Dict, Optional

import discord

from cache import messages
from database import users
from resources import exceptions, regex


async def process_message(bot: discord.Bot, message: discord.Message, embed_data: Dict, user: Optional[discord.User],
                          user_settings: Optional[users.User]) -> bool:
    """Processes the message for all inventory related actions.

    Returns
    -------
    - True if a logo reaction should be added to the message
    - False otherwise
    """
    return_values = []
    return_values.append(await update_inventory(message, embed_data, user, user_settings))
    return any(return_values)


async def update_inventory(message: discord.Message, embed_data: Dict, interaction_user: Optional[discord.User],
                           user_settings: Optional[users.User]) -> bool:
    """Updates data from inventory

    Returns
    -------
    - False
    """
    add_reaction = False
    if interaction_user is not None: return add_reaction
    search_strings_author = [
        '— inventory', #English
    ]
    search_strings_items = [
        'wood', #Materials
        '⚠', #Materials in debt
    ]
    if (any(search_string in embed_data['author']['name'].lower() for search_string in search_strings_author)
        and any(search_string in embed_data['field0']['name'].lower() for search_string in search_strings_items)):
        if interaction_user is None:
            user_command_message = (
                await messages.find_message(message.channel.id, regex.COMMAND_INVENTORY)
            )
            interaction_user = user_command_message.author
        if embed_data['embed_user'] is not None and embed_data['embed_user'] != interaction_user: return add_reaction
        if interaction_user.name not in embed_data['author']['name']: return
        if user_settings is None:
            try:
                user_settings: users.User = await users.get_user(interaction_user.id)
            except exceptions.FirstTimeUserError:
                return add_reaction
        if not user_settings.bot_enabled: return add_reaction
        inventory_fields = ''
        for field in message.embeds[0].fields:
            inventory_fields = f'{inventory_fields}\n{field.value}'.strip()
        item_debt = True if '⚠' in embed_data['field0']['name'].lower() else False
        if 'guild seal' not in inventory_fields.lower():
            if item_debt and user_settings.inventory.guild_seal < 0:
                guild_seal_count = 0
            elif not item_debt and user_settings.inventory.guild_seal > 0:
                guild_seal_count = 0
            else:
                guild_seal_count = user_settings.inventory.guild_seal
        else:
            guild_seal_count_match = re.search(r"guild seal\*\*: ([\-0-9,]+)", inventory_fields.lower())
            guild_seal_count = int(guild_seal_count_match.group(1).replace(',',''))
        if user_settings.inventory.guild_seal != guild_seal_count:
            await user_settings.update(inventory_guild_seal=guild_seal_count)
            if user_settings.reactions_enabled: add_reaction = True
    return add_reaction