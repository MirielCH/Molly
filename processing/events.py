# events.py

from typing import Dict

import discord

from database import guilds


async def process_message(bot: discord.Bot, message: discord.Message, embed_data: Dict, guild_settings: guilds.Guild) -> bool:
    """Processes the message for all event related actions.

    Returns
    -------
    - True if a logo reaction should be added to the message
    - False otherwise
    """
    return_values = []
    return_values.append(await send_event_ping(message, embed_data, guild_settings))
    return any(return_values)


async def send_event_ping(message: discord.Message, embed_data: Dict, guild_settings: guilds.Guild) -> bool:
    """Sends an event ping

    Returns
    -------
    - True if a logo reaction should be added to the message
    - False otherwise
    """
    add_reaction = False
    search_strings_name = {
        'say ohmmm': 'energy', #English
        'fired from its farm': 'hire', #English
        'lucky reward!': 'lucky', #English
        'quatrillion of items': 'packing', #English
    }
    search_strings_value = (
        'an energy ritual has started', #English
        'reserved only for the first player who claims it!', #English
        'a lucky reward will be given to one of the players who joins!', #English
        'help to make boxes and get packing xp!', #English
    )
    if (any(search_string in embed_data['field0']['name'].lower() for search_string in search_strings_name.keys())
        and any(search_string in embed_data['field0']['value'].lower()for search_string in search_strings_value)):
        for string, event_name in search_strings_name.items():
            if string in embed_data['field0']['name'].lower():
                event = event_name
                break
        event_settings = getattr(guild_settings, f'event_{event}', None)
        if event_settings is None: return add_reaction
        if not event_settings.enabled: return add_reaction
        allowed_mentions = discord.AllowedMentions(everyone=True, roles=True)
        await message.reply(event_settings.message, allowed_mentions=allowed_mentions)
    return add_reaction