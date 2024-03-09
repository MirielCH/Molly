# claim.py

from datetime import timedelta
import re
from typing import Dict, Optional

import discord
from discord import utils

from cache import messages
from database import users
from resources import exceptions, functions, regex, settings, strings, views


async def process_message(bot: discord.Bot, message: discord.Message, embed_data: Dict, user: Optional[discord.User] = None,
                          user_settings: Optional[users.User] = None) -> bool:
    """Processes the message for all daily related actions.

    Returns
    -------
    - True if a logo reaction should be added to the message
    - False otherwise
    """
    return_values = []
    return_values.append(await process_claim_message(bot, message, embed_data, user, user_settings))
    return any(return_values)


async def process_claim_message(bot: discord.Bot, message: discord.Message, embed_data: Dict, user: Optional[discord.User],
                                user_settings: Optional[users.User]) -> bool:
    """Tracks last claim time, updates energy loss and creates a claim reminder if the user so desires

    Returns
    -------
    - True if a logo reaction should be added to the message
    - False otherwise
    """
    add_reaction = False
    search_strings = [
        '— claim', #English
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
                    await messages.find_message(message.channel.id, regex.COMMAND_CLAIM, user_name=user_name)
                )
                user = user_command_message.author
        if user_settings is None:
            try:
                user_settings: users.User = await users.get_user(user.id)
            except exceptions.FirstTimeUserError:
                return add_reaction
        if not user_settings.bot_enabled: return add_reaction
        claim_fields = ''
        for field in message.embeds[0].fields:
            claim_fields = f'{claim_fields}\n{field.value}'.strip()
            guild_seal_count_match = re.search(r"\+([0-9,]+) <:guildseal", claim_fields.lower())
            if guild_seal_count_match:
                guild_seal_count = int(guild_seal_count_match.group(1).replace(',',''))
                guild_seal_count = user_settings.inventory.guild_seal + guild_seal_count
            else:
                guild_seal_count = user_settings.inventory.guild_seal
        await user_settings.update(last_claim_time=message.created_at, time_speeders_used=0, time_compressors_used=0,
                                   time_dilators_used=0, inventory_guild_seal=guild_seal_count)
        try:
            await functions.change_user_energy(user_settings, -5)
            if not user_settings.reminder_claim.enabled and user_settings.reactions_enabled: add_reaction = True
        except exceptions.EnergyFullTimeOutdatedError:
            await message.reply(strings.MSG_ENERGY_OUTDATED.format(user=user.display_name,
                                                                    cmd_profile=strings.SLASH_COMMANDS["profile"]))
        except exceptions.EnergyFullTimeNoneError:
            pass
        if user_settings.reminder_claim.enabled:
            view = views.SetClaimReminderTimeView(bot, message, user, user_settings)
            embed = discord.Embed(
                color = settings.EMBED_COLOR,
                title = 'Nice claim!',
                description = (
                    f'When would you like to be reminded for your next claim?'
                )
            )
            interaction = await message.reply(embed=embed, view=view)
            view.interaction = interaction
            await view.wait()
    return add_reaction