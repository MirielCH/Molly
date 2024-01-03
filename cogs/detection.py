# detection.py
"""Collects and parses IDLE FARM messages"""

import re
from typing import Dict, Union

import discord
from discord.ext import commands

from database import clans, guilds, users
from processing import activities, boosts, buy, claim, clan, daily, donate, events, halloween, open, payday, profile, raid
from processing import request, shop, teamraid, upgrades, use, vote, workers, xmas
from resources import exceptions, functions, logs, regex, settings


class DetectionCog(commands.Cog):
    """Cog that contains the detection events"""
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message_edit(self, message_before: discord.Message, message_after: discord.Message) -> None:
        """Runs when a message is edited in a channel."""
        if message_after.author.id not in [settings.GAME_ID, settings.TESTY_ID]: return
        embed_data_before = await parse_embed(message_before)
        embed_data = await parse_embed(message_after)
        if (message_before.content == message_after.content and embed_data_before == embed_data
            and message_before.components == message_after.components): return
        if await check_edited_message_never_allowed(message_before, message_after, embed_data): return
        if await check_edited_message_always_allowed(message_before, message_after, embed_data):
            await self.on_message(message_after)
            return
        if message_before.components and not message_after.components: return
        if await check_message_for_active_components(message_after):
            await self.on_message(message_after)
            return

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        """Runs when a message is sent in a channel."""
        if message.author.id not in [settings.GAME_ID, settings.TESTY_ID]: return
        user_settings = clan_settings = None
        embed_data = await parse_embed(message)
        embed_data['embed_user'] = None
        embed_data['embed_user_settings'] = None
        interaction_user = await functions.get_interaction_user(message)
        user_id_match = re.search(regex.USER_ID_FROM_ICON_URL, embed_data['author']['icon_url'])
        if user_id_match:
            embed_data['embed_user'] = message.guild.get_member(int(user_id_match.group(1)))
        if interaction_user is not None:
            try:
                user_settings: users.User = await users.get_user(interaction_user.id)
            except exceptions.FirstTimeUserError:
                return
            if user_settings is not None:
                if not user_settings.bot_enabled: return
            try:
                clan_settings: clans.Clan = await clans.get_clan_by_member_id(interaction_user.id)
            except exceptions.NoDataFoundError:
                pass
        if embed_data['embed_user'] is not None:
            if interaction_user is not None and embed_data['embed_user'] == interaction_user:
                embed_user_settings = user_settings
            else:
                try:
                    embed_user_settings: users.User = await users.get_user(embed_data['embed_user'].id)
                except exceptions.FirstTimeUserError:
                    embed_user_settings = None
            embed_data['embed_user_settings'] = embed_user_settings
        guild_settings = await guilds.get_guild(message.guild.id)
        return_values = []
        helper_context_enabled = getattr(user_settings, 'helper_context_enabled', True)
        helper_profile_enabled = getattr(user_settings, 'helper_profile_enabled', True)
        helper_raid_enabled = getattr(user_settings, 'helper_raid_enabled', True)
        helper_upgrades_enabled = getattr(user_settings, 'helper_upgrades_enabled', True)
        reminder_daily_enabled = getattr(getattr(user_settings, 'reminder_daily', None), 'enabled', True)
        reminder_claim_enabled = getattr(getattr(user_settings, 'reminder_claim', None), 'enabled', True)
        reminder_energy_enabled = getattr(getattr(user_settings, 'reminder_energy', None), 'enabled', True)
        reminder_shop_enabled = getattr(getattr(user_settings, 'reminder_shop', None), 'enabled', True)
        reminder_vote_enabled = getattr(getattr(user_settings, 'reminder_vote', None), 'enabled', True)
        tracking_enabled = getattr(user_settings, 'tracking_enabled', True)
        helper_teamraid_enabled = getattr(clan_settings, 'helper_teamraid_enabled', False)

        # Raids
        if tracking_enabled or helper_context_enabled or helper_raid_enabled or reminder_energy_enabled:
            add_reaction = await raid.process_message(self.bot, message, embed_data, interaction_user, user_settings)
            return_values.append(add_reaction)

        # Claim Reminder
        add_reaction = await claim.process_message(self.bot, message, embed_data, interaction_user, user_settings)
        return_values.append(add_reaction)

        # Daily Reminder
        if reminder_daily_enabled:
            add_reaction = await daily.process_message(self.bot, message, embed_data, interaction_user, user_settings)
            return_values.append(add_reaction)
            
        # Shop Reminder
        if reminder_shop_enabled:
            add_reaction = await shop.process_message(self.bot, message, embed_data, interaction_user, user_settings)
            return_values.append(add_reaction)

        # Use items
        add_reaction = await use.process_message(self.bot, message, embed_data, interaction_user, user_settings)
        return_values.append(add_reaction)
        
        # Payday
        if helper_upgrades_enabled:
            add_reaction = await payday.process_message(self.bot, message, embed_data, interaction_user, user_settings)
            return_values.append(add_reaction)
        
        # Buy items frop the shop
        if helper_context_enabled:
            add_reaction = await buy.process_message(self.bot, message, embed_data, interaction_user, user_settings)
            return_values.append(add_reaction)

        # Event pings
        if any([guild_settings.event_energy.enabled, guild_settings.event_hire.enabled,
                guild_settings.event_lucky.enabled, guild_settings.event_packing.enabled]):
            add_reaction = await events.process_message(self.bot, message, embed_data, guild_settings)
            return_values.append(add_reaction)
            
        # Track upgrades
        if helper_upgrades_enabled:
            add_reaction = await upgrades.process_message(self.bot, message, embed_data, interaction_user, user_settings)
            return_values.append(add_reaction)

        # Open    
        if helper_raid_enabled or helper_teamraid_enabled:
            add_reaction = await open.process_message(self.bot, message, embed_data, interaction_user, user_settings,
                                                      clan_settings)
            return_values.append(add_reaction)

        # Request tracking
        if helper_raid_enabled or helper_teamraid_enabled:
            add_reaction = await request.process_message(self.bot, message, embed_data, interaction_user, user_settings,
                                                         clan_settings)
            return_values.append(add_reaction)

        # Vote
        if reminder_vote_enabled:
            add_reaction = await vote.process_message(self.bot, message, embed_data, interaction_user, user_settings)
            return_values.append(add_reaction)
            
        # Worker tracking
        add_reaction = await workers.process_message(self.bot, message, embed_data, interaction_user, user_settings,
                                                        clan_settings)
        return_values.append(add_reaction)

        # Clan reminders & updates
        add_reaction = await clan.process_message(self.bot, message, embed_data, interaction_user, user_settings,
                                                  clan_settings)
        return_values.append(add_reaction)
        add_reaction = await teamraid.process_message(self.bot, message, embed_data, interaction_user, user_settings,
                                                      clan_settings)
        return_values.append(add_reaction)

        # Update donor tier
        add_reaction = await donate.process_message(self.bot, message, embed_data, interaction_user, user_settings)
        return_values.append(add_reaction)

         # Energy Helper
        add_reaction = await profile.process_message(self.bot, message, embed_data, interaction_user, user_settings)
        return_values.append(add_reaction)
        
         # Boost reminders
        add_reaction = await boosts.process_message(self.bot, message, embed_data, interaction_user, user_settings)
        return_values.append(add_reaction)
        
         # Halloween
        add_reaction = await halloween.process_message(self.bot, message, embed_data, interaction_user, user_settings)
        return_values.append(add_reaction)
        
         # Christmas
        add_reaction = await xmas.process_message(self.bot, message, embed_data, interaction_user, user_settings)
        return_values.append(add_reaction)

        # Activity list
        add_reaction = await activities.process_message(self.bot, message, embed_data, interaction_user, user_settings)
        return_values.append(add_reaction)

        if any(return_values): await functions.add_logo_reaction(message)

# Initialization
def setup(bot):
    bot.add_cog(DetectionCog(bot))


# Functions
async def parse_embed(message: discord.Message) -> Dict[str, str]:
    """Parses all data from an embed into a dictionary.
    All keys are guaranteed to exist and have an empty string as value if not set in the embed.
    """
    embed_data = {
        'author': {'icon_url': '', 'name': ''},
        'description': '',
        'field0': {'name': '', 'value': ''},
        'field1': {'name': '', 'value': ''},
        'field2': {'name': '', 'value': ''},
        'field3': {'name': '', 'value': ''},
        'field4': {'name': '', 'value': ''},
        'field5': {'name': '', 'value': ''},
        'footer': {'icon_url': '', 'text': ''},
        'title': '',
    }
    if message.embeds:
        embed = message.embeds[0]
        if embed.author is not None:
            if embed.author.icon_url is not None:
                embed_data['author']['icon_url'] = embed.author.icon_url
            if embed.author.name is not None:
                embed_data['author']['name'] = embed.author.name
        if embed.description is not None:
            embed_data['description'] = embed.description
        if embed.fields:
            try:
                embed_data['field0']['name'] = embed.fields[0].name
                embed_data['field0']['value'] = embed.fields[0].value
            except IndexError:
                pass
            try:
                embed_data['field1']['name'] = embed.fields[1].name
                embed_data['field1']['value'] = embed.fields[1].value
            except IndexError:
                pass
            try:
                embed_data['field2']['name'] = embed.fields[2].name
                embed_data['field2']['value'] = embed.fields[2].value
            except IndexError:
                pass
            try:
                embed_data['field3']['name'] = embed.fields[3].name
                embed_data['field3']['value'] = embed.fields[3].value
            except IndexError:
                pass
            try:
                embed_data['field4']['name'] = embed.fields[4].name
                embed_data['field4']['value'] = embed.fields[4].value
            except IndexError:
                pass
            try:
                embed_data['field5']['name'] = embed.fields[5].name
                embed_data['field5']['value'] = embed.fields[5].value
            except IndexError:
                pass
        if embed.footer is not None:
            if embed.footer.icon_url is not None:
                embed_data['footer']['icon_url'] = embed.footer.icon_url
            if embed.footer.text is not None:
                embed_data['footer']['text'] = embed.footer.text
        if embed.title is not None:
            embed_data['title'] = embed.title
    return embed_data


async def check_message_for_active_components(message: discord.Message) -> Union[bool, None]:
    """Checks if the message has any active components.

    Returns
    -------
    - False if all components are disabled
    - True if at least one component is not disabled OR the message doesn't have any components
    """
    if not message.components: return True
    active_component = False
    for row in message.components:
        for component in row.children:
            if not component.disabled:
                active_component = True
                break
    return active_component


async def check_edited_message_always_allowed(message_before: discord.Message,
                                             message_after: discord.Message, embed_data: Dict) -> Union[bool, None]:
    """Check if the edited message should be allowed to process regardless of its components.

    Returns
    -------
    - True if allowed
    - False if not affected by this check
    """
    search_strings =  [
        '— worker roll', #All languages
    ]
    if any(search_string in embed_data['author']['name'].lower() for search_string in search_strings):
        if message_before.embeds[0].footer is not None:
            if message_before.embeds[0].footer.text != embed_data['footer']['text']: return True
    return False


async def check_edited_message_never_allowed(message_before: discord.Message,
                                             message_after: discord.Message, embed_data: Dict) -> Union[bool, None]:
    """Check if the edited message should never be allowed to process.

    Returns
    -------
    - True if never allowed
    - False if not affected by this check
    """
    if message_before.pinned != message_after.pinned: return True
    search_strings =  [
        '— raid', #All languages
    ]
    if any(search_string in embed_data['author']['name'].lower() for search_string in search_strings):
        return True
    """
    search_strings =  [
        '— worker roll', #All languages
    ]
    if (any(search_string in embed_data['author']['name'].lower() for search_string in search_strings)
           and '(+' in embed_data['field0']['value']):
        return True
    """
    return False