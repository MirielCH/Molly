# buy.py

import re
from typing import Dict, Optional

import discord

from database import users
from resources import exceptions, strings


async def process_message(message: discord.Message, embed_data: Dict, user: Optional[discord.User],
                          user_settings: Optional[users.User]) -> bool:
    """Processes the message for all /shop buy related actions.

    Returns
    -------
    - True if a logo reaction should be added to the message
    - False otherwise
    """
    return_values = []
    return_values.append(await call_context_helper(message, embed_data, user, user_settings))
    return any(return_values)


async def call_context_helper(message: discord.Message, embed_data: Dict, user: Optional[discord.User],
                                              user_settings: Optional[users.User]) -> bool:
    """Call the context helper when buying an item

    Returns
    -------
    - True if a logo reaction should be added to the message
    - False otherwise
    """
    add_reaction = False
    search_strings = [
        'successfully bought', #English
    ]
    if (any(search_string in message.content.lower() for search_string in search_strings)
        and 'idlecoin' in message.content.lower()):
        if user is None: user = message.mentions[0]
        if user_settings is None:
            try:
                user_settings: users.User = await users.get_user(user.id)
            except exceptions.FirstTimeUserError:
                return add_reaction
        if not user_settings.bot_enabled or not user_settings.helper_context_enabled: return add_reaction
        item_name_match = re.search(r'\s`(.+?)`\s', message.content.lower())
        items_commands = {
            'energy glass': f"➜ {strings.SLASH_COMMANDS['use']}\n",
            'energy drink': f"➜ {strings.SLASH_COMMANDS['use']}\n",
            'energy galloon': f"➜ {strings.SLASH_COMMANDS['use']}\n",
            'common lootbox': f"➜ {strings.SLASH_COMMANDS['open']}\n",
            'mythic lootbox': f"➜ {strings.SLASH_COMMANDS['open']}\n",
            'time speeder': f"➜ {strings.SLASH_COMMANDS['use']}\n",
        }
        item_name = item_name_match.group(1)
        if item_name not in items_commands: return add_reaction
        await message.reply(items_commands[item_name])
    return add_reaction