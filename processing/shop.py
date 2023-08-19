# shop.py

from datetime import timedelta
import random
import re
from typing import Dict, Optional

import discord
from discord import utils

from cache import messages
from database import reminders, users
from resources import exceptions, functions, regex, strings


async def process_message(bot: discord.Bot, message: discord.Message, embed_data: Dict, user: Optional[discord.User],
                          user_settings: Optional[users.User]) -> bool:
    """Processes the message for all shop related actions.

    Returns
    -------
    - True if a logo reaction should be added to the message
    - False otherwise
    """
    return_values = []
    return_values.append(await create_reminder_from_buying(message, embed_data, user, user_settings))
    return_values.append(await create_reminder_from_list(message, embed_data, user, user_settings))
    return any(return_values)


async def create_reminder_from_buying(message: discord.Message, embed_data: Dict, user: Optional[discord.User],
                          user_settings: Optional[users.User]) -> bool:
    """Create a reminder when the user tries to buy an item that is out of stock.
    This only works with prefix command because I can't read the slash command option

    Returns
    -------
    - True if a logo reaction should be added to the message
    - False otherwise
    """
    add_reaction = False
    search_strings = [
        'maxed the purchases', #All languages
    ]
    if any(search_string in message.content.lower() for search_string in search_strings):
        if user is not None:
            if user_settings is None:
                try:
                    user_settings: users.User = await users.get_user(user.id)
                except exceptions.FirstTimeUserError:
                    return add_reaction
            if not user_settings.reminder_shop.enabled:
                await message.reply(
                    f'**{user.name}**, please use {strings.SLASH_COMMANDS["shop list"]} to create a reminder.'
                )
                return add_reaction
        user = message.mentions[0]
        user_command_message = (
            await messages.find_message(message.channel.id, regex.COMMAND_SHOP, user=user)
        )
        if user_settings is None:
            try:
                user_settings: users.User = await users.get_user(user.id)
            except exceptions.FirstTimeUserError:
                return add_reaction
        if not user_settings.bot_enabled or not user_settings.reminder_shop.enabled: return add_reaction
        item_name_match = re.search(r'\bbuy\b\s+\b(.+?)$', user_command_message.content.lower())
        item_name = item_name_match.group(1)
        timestring_match = re.search(r'🕓\s\*\*(.+?)\*\*\n', message.content.lower())
        timestring = timestring_match.group(1)
        time_left = await functions.calculate_time_left_from_timestring(message, timestring)
        time_left += timedelta(seconds=random.randint(60, 300))
        user_command = await functions.get_game_command(user_settings, 'shop buy')
        reminder_message = (
            user_settings.reminder_shop.message
            .replace('{command}', user_command)
            .replace('{shop_item}', item_name)
        )
        reminder: reminders.Reminder = (
            await reminders.insert_user_reminder(user.id, f'shop-{item_name.replace(" ","-")}', time_left,
                                                    message.channel.id, reminder_message)
        )
        if reminder.record_exists and user_settings.reactions_enabled: add_reaction = True
    return add_reaction


async def create_reminder_from_list(message: discord.Message, embed_data: Dict, user: Optional[discord.User],
                          user_settings: Optional[users.User]) -> bool:
    """Create a reminder when an item in the shop is out of stock

    Returns
    -------
    - True if a logo reaction should be added to the message
    - False otherwise
    """
    add_reaction = False
    search_strings = [
        'buy anything with `idle shop buy [item]`', #All languages
    ]
    if (any(search_string in embed_data['description'].lower() for search_string in search_strings)
        and message.embeds):
        if user is None:
            user_command_message = (
                await messages.find_message(message.channel.id, regex.COMMAND_SHOP)
            )
            user = user_command_message.author
        if user_settings is None:
            try:
                user_settings: users.User = await users.get_user(user.id)
            except exceptions.FirstTimeUserError:
                return add_reaction
        if not user_settings.bot_enabled or not user_settings.reminder_shop.enabled: return add_reaction
        user_command = await functions.get_game_command(user_settings, 'shop buy')
        current_time = utils.utcnow()
        midnight_today = utils.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        midnight_tomorrow = midnight_today + timedelta(days=1)
        for field in message.embeds[0].fields:
            shop_item_data_match = re.search(r'__\*\*(.+?)\*\*__.+`(\d+?)/(\d+?)`.+\*\*(.+?)\*\*', field.value.lower(),
                                             re.DOTALL)
            if not shop_item_data_match: continue
            item_name = shop_item_data_match.group(1).strip()
            item_amount_bought = int(shop_item_data_match.group(2))
            item_amount_available = int(shop_item_data_match.group(3))
            timestring = shop_item_data_match.group(4)
            if item_amount_bought < item_amount_available: continue
            time_left_timestring = await functions.parse_timestring_to_timedelta(timestring)
            time_left = midnight_tomorrow - current_time  + timedelta(seconds=random.randint(60, 300))
            if time_left_timestring >= timedelta(days=1):
                time_left = time_left + timedelta(days=time_left_timestring.days)
            reminder_message = (
                user_settings.reminder_shop.message
                .replace('{command}', user_command)
                .replace('{shop_item}', item_name)
            )
            reminder: reminders.Reminder = (
                await reminders.insert_user_reminder(user.id, f'shop-{item_name.replace(" ","-")}', time_left,
                                                     message.channel.id, reminder_message)
            )
            if reminder.record_exists and user_settings.reactions_enabled: add_reaction = True
    return add_reaction