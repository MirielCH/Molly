# claim.py

import re
from typing import Dict, Optional

import discord
from discord import utils

from cache import messages
from database import users
from resources import exceptions, regex, settings, views


async def process_message(message: discord.Message, embed_data: Dict, user: Optional[discord.User] = None,
                          user_settings: Optional[users.User] = None) -> bool:
    """Processes the message for all daily related actions.

    Returns
    -------
    - True if a logo reaction should be added to the message
    - False otherwise
    """
    return_values = []
    return_values.append(await process_claim_message(message, embed_data, user, user_settings))
    return any(return_values)


async def process_claim_message(message: discord.Message, embed_data: Dict, user: Optional[discord.User],
                                user_settings: Optional[users.User]) -> bool:
    """Tracks last claim time and creates a claim reminder if the user so desires

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
                user_id_match = re.search(regex.USER_ID_FROM_ICON_URL, embed_data['author']['icon_url'])
                if user_id_match:
                    user_id = int(user_id_match.group(1))
                    user = message.guild.get_member(user_id)
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
        await user_settings.update(last_claim_time=message.created_at)
        await user_settings.update(time_speeders_used=0)
        if not user_settings.reminder_claim.enabled: return add_reaction
        view = views.SetClaimReminderTimeView(message, user, user_settings)
        current_time = utils.utcnow()
        embed = discord.Embed(
            color = settings.EMBED_COLOR,
            #title = f'Time to {await functions.get_game_command(user_settings, "claim")}!',
            title = 'Nice claim!',
            description = (
                f'When would you like to be reminded for your next claim?'
            )
            #description = (
                #f'**Time to {await functions.get_game_command(user_settings, "claim")}!**\n'
            #    f'• Your last claim was {utils.format_dt(user_settings.last_claim_time, "R")}\n'
            #    f'• Your farms produced {format_timespan(current_time - user_settings.last_claim_time + user_settings.time_speeders_used * timedelta(hours=2))} of items.'
            #)
        )
        #img_logo = discord.File(settings.IMG_LOGO, filename='logo.png')
        #image_url = 'attachment://logo.png'
        #embed.set_thumbnail(url=image_url)
        interaction = await message.reply(embed=embed, view=view)
        view.interaction = interaction
        await view.wait()
    return add_reaction