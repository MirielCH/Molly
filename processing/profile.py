# profile.py

import re
from typing import Dict, Optional

import discord

from cache import messages
from database import users
from resources import exceptions, regex


async def process_message(bot: discord.Bot, message: discord.Message, embed_data: Dict, user: Optional[discord.User],
                          user_settings: Optional[users.User]) -> bool:
    """Processes the message for all profile related actions.

    Returns
    -------
    - True if a logo reaction should be added to the message
    - False otherwise
    """
    return_values = []
    return_values.append(await update_idlucks(message, embed_data, user, user_settings))
    return any(return_values)


async def update_idlucks(message: discord.Message, embed_data: Dict, user: Optional[discord.User],
                         user_settings: Optional[users.User]) -> bool:
    """Create a reminder on /daily

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
                        await messages.find_message(message.channel.id, regex.COMMAND_PROFILE, user_name=user_name)
                    )
                    user = user_command_message.author
        if user_settings is None:
            try:
                user_settings: users.User = await users.get_user(user.id)
            except exceptions.FirstTimeUserError:
                return add_reaction
        if not user_settings.bot_enabled: return add_reaction
        idlucks_match = re.search(r'idlucks\*\*: ([0-9,]+?)\n', embed_data['field3']['value'].lower())
        idlucks = int(re.sub('\D','', idlucks_match.group(1)))
        await user_settings.update(idlucks=idlucks)
        """
        energy_match = re.search(r'1084593332312887396> (\d+)/(\d+)\n', embed_data['field0']['value'])
        energy_current, energy_max = energy_match.groups()
        energy_regen = 6 / (1.5 * 1.0)
        minutes_until_max = (int(energy_max) - int(energy_current)) * energy_regen
        time_until_limit = utils.utcnow() + timedelta(minutes=minutes_until_max)
        embed = discord.Embed(
            color=settings.EMBED_COLOR,
            title='Your energy',
            description=(
              f'{emojis.DETAIL2} You generate 1 energy every {format_timespan(timedelta(minutes=energy_regen))}.\n'
              f'{emojis.DETAIL} Assuming you will idle, you will hit the energy limit {utils.format_dt(time_until_limit, "R")}'
            ),
        )
        await message.reply(embed=embed)
        """
    return add_reaction