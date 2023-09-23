# profile.py

from datetime import timedelta
import re
from typing import Dict, Optional

import discord
from discord import utils

from cache import messages
from database import clans, reminders, upgrades, users
from resources import emojis, exceptions, functions, regex, settings, strings, views


async def process_message(bot: discord.Bot, message: discord.Message, embed_data: Dict, user: Optional[discord.User],
                          user_settings: Optional[users.User]) -> bool:
    """Processes the message for all profile related actions.

    Returns
    -------
    - True if a logo reaction should be added to the message
    - False otherwise
    """
    return_values = []
    return_values.append(await call_profile_timers_and_update_idlucks(bot, message, embed_data, user, user_settings))
    return any(return_values)


async def call_profile_timers_and_update_idlucks(bot: discord.Bot, message: discord.Message, embed_data: Dict,
                                                 interaction_user: Optional[discord.User],
                                                 user_settings: Optional[users.User]) -> bool:
    """• Update idluck count in the database
    • Show profile timers helper

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
        if interaction_user is None:
            user_command_message = (
                await messages.find_message(message.channel.id, regex.COMMAND_PROFILE)
            )
            if user_command_message is None: return add_reaction
            interaction_user = user_command_message.author
        if embed_data['embed_user'] is not None and embed_data['embed_user'] != interaction_user: return add_reaction
        if user_settings is None:
            try:
                user_settings: users.User = await users.get_user(interaction_user.id)
            except exceptions.FirstTimeUserError:
                return add_reaction
        if not user_settings.bot_enabled: return add_reaction
        if user_settings.helper_upgrades_enabled:
            idlucks_match = re.search(r'idlucks\*\*: ([0-9,]+?)\n', embed_data['field3']['value'].lower())
            idlucks = int(re.sub('\D','', idlucks_match.group(1)))
            await user_settings.update(idlucks=idlucks)
        if not user_settings.helper_profile_enabled and not user_settings.reminder_energy.enabled:
            return add_reaction
        
        energy_match = re.search(r'1084593332312887396> ([0-9,]+)/([0-9,]+)\n', embed_data['field0']['value'])
        energy_current = int(re.sub('\D','',energy_match.group(1)))
        energy_max = int(re.sub('\D','',energy_match.group(2)))
        try:
            energy_upgrade: upgrades.Upgrade = await upgrades.get_upgrade(user_settings.user_id, 'energy regeneration')
            multiplier_upgrade = strings.ENERGY_UPGRADE_LEVEL_MULTIPLIERS[energy_upgrade.level]
        except exceptions.NoDataFoundError:
            multiplier_upgrade = 1
        multiplier_donor = list(strings.DONOR_TIER_ENERGY_MULTIPLIERS.values())[user_settings.donor_tier]
        energy_regen = 5 / (multiplier_donor * multiplier_upgrade)
        minutes_until_max = (int(energy_max) - int(energy_current)) * energy_regen
        current_time = utils.utcnow()
        level_full_time = current_time + timedelta(minutes=minutes_until_max)
        energy_regen_time = timedelta(minutes=energy_regen)
        await user_settings.update(energy_max=energy_max, energy_full_time=level_full_time)
        try:
            await functions.recalculate_energy_reminder(user_settings, energy_regen_time)
        except exceptions.EnergyFullTimeOutdatedError:
            pass
        if user_settings.reactions_enabled and not user_settings.helper_profile_enabled:
            add_reaction = True
        
        if user_settings.helper_profile_enabled:
            # Energy level
            if energy_current >= 5:
                level_claim_info = f'{emojis.ENABLED} **Claim** (5)'
            else:
                minutes_until_claim = int(5 - energy_current) * energy_regen
                level_claim_time = current_time + timedelta(minutes=minutes_until_claim)
                level_claim_info = f'{emojis.COOLDOWN} **Claim** (5) {utils.format_dt(level_claim_time, "R")}'
            if energy_current >= 40:
                level_raid_info = f'{emojis.ENABLED} **Raid** (40)'
            else:
                minutes_until_raid = int(40 - energy_current) * energy_regen
                level_raid_time = current_time + timedelta(minutes=minutes_until_raid)
                level_raid_info = f'{emojis.COOLDOWN} **Raid** (40) {utils.format_dt(level_raid_time, "R")}'
            if energy_current >= 80:
                level_teamraid_info = f'{emojis.ENABLED} **Teamraid** (80)'
            else:
                minutes_until_teamraid = int(80 - energy_current) * energy_regen
                level_teamraid_time = current_time + timedelta(minutes=minutes_until_teamraid)
                level_teamraid_info = f'{emojis.COOLDOWN} **Teamraid** (80) {utils.format_dt(level_teamraid_time, "R")}'
            energy_level = f'{level_claim_info} | {level_raid_info} | {level_teamraid_info}'
            energy_level = f'{level_claim_info}\n{level_raid_info}\n{level_teamraid_info}'
            if energy_current >= energy_max:
                energy_level = f'{emojis.WARNING} **FULL!**'
            else:
                energy_level = f'{energy_level}\n{emojis.COOLDOWN} **Full** ({user_settings.energy_max}) {utils.format_dt(level_full_time, "R")}'
            try:
                energy_reminder: reminders.Reminder = await reminders.get_user_reminder(interaction_user.id, 'energy')
                if energy_reminder.end_time > current_time:
                    energy_level = (
                        f'{energy_level}\n'
                        f'{emojis.COOLDOWN} **Reminder** ({energy_reminder.activity[7:]}) {utils.format_dt(energy_reminder.end_time, "R")}'
                    )
            except exceptions.NoDataFoundError:
                pass
            
            last_claim_time_timestamp = 'Never'
            time_produced_timespan = 'None'
            if user_settings.last_claim_time is not None:
                time_since_last_claim = current_time - user_settings.last_claim_time
                last_claim_time_timestamp = utils.format_dt(user_settings.last_claim_time, 'R')
                time_produced = (time_since_last_claim + user_settings.time_speeders_used * timedelta(hours=2)
                                 + user_settings.time_compressors_used * timedelta(hours=4))
                if time_produced >= timedelta(hours=24): time_produced = timedelta(hours=24)
                time_produced_timestring = (
                    await functions.parse_timedelta_to_timestring(time_produced - timedelta(microseconds=time_produced.microseconds))
                )
                time_produced_timespan = (
                    f'`{time_produced_timestring}` ({user_settings.time_speeders_used}{emojis.TIME_SPEEDER} '
                    f'| {user_settings.time_compressors_used}{emojis.TIME_COMPRESSOR})'
                )
                
            embed = discord.Embed(
                color=settings.EMBED_COLOR,
            )
            embed.add_field(
                name = 'Energy level',
                value = f'{energy_level}\n',
                inline = False
            )

            field_production = (
                f'{emojis.BP} **Last claim**: {last_claim_time_timestamp}\n'
                f'{emojis.BP} **Production time**: {time_produced_timespan}'
            )
            try:
                claim_reminder: reminders.Reminder = await reminders.get_user_reminder(interaction_user.id, 'claim')
                if claim_reminder.end_time > current_time:
                    field_production = (
                        f'{field_production}\n'
                        f'{emojis.COOLDOWN} **Reminder** {utils.format_dt(claim_reminder.end_time, "R")}'
                    )
            except exceptions.NoDataFoundError:
                pass
            embed.add_field(
                name = 'Production',
                value = field_production,
                inline = False
            )
            if user_settings.helper_profile_ready_commands_visible:
                ready_activities = []
                if user_settings.reminder_claim.enabled:
                    ready_activities.append('claim')
                if user_settings.reminder_daily.enabled:
                    ready_activities.append('daily')
                clan_settings = None
                try:
                    clan_settings: clans.Clan = await clans.get_clan_by_member_id(interaction_user.id)
                except exceptions.NoDataFoundError:
                    pass
                if clan_settings is not None:
                    if clan_settings.reminder_enabled:
                        ready_activities.append('teamraid')
                if user_settings.reminder_vote.enabled:
                    ready_activities.append('vote')
                try:
                    active_reminders = await reminders.get_active_user_reminders(interaction_user.id)
                    for reminder in active_reminders:
                        if reminder.activity in ready_activities:
                            ready_activities.remove(reminder.activity)
                except exceptions.NoDataFoundError:
                    pass
                clan_reminder = None
                if clan_settings is not None:
                    try:
                        clan_reminder = await reminders.get_clan_reminder(clan_settings.clan_name)
                    except exceptions.NoDataFoundError:
                        pass
                if clan_reminder is not None and 'teamraid' in ready_activities:
                    ready_activities.remove('teamraid')
                if ready_activities:
                    field_ready_commands = ''
                    for activity in ready_activities:
                        field_ready_commands = (
                            f'{field_ready_commands}\n'
                            f'{emojis.ENABLED} {strings.SLASH_COMMANDS[f"{activity}"]}'
                        )
                    embed.add_field(
                        name = 'Ready commands',
                        value = field_ready_commands.strip(),
                        inline = False
                    )
            percentage_donor = round((multiplier_donor - 1) * 100)
            percentage_upgrade = round((multiplier_upgrade - 1) * 100)
            if energy_regen_time.microseconds > 0:
                energy_regen_time = energy_regen_time + timedelta(microseconds=1_000_000 - energy_regen_time.microseconds)
            energy_regen_timestring = await functions.parse_timedelta_to_timestring(energy_regen_time)
            embed.set_footer(text=f'1 energy per {energy_regen_timestring} (+{percentage_donor}% donor | +{percentage_upgrade}% upgrades)')
            if user_settings.reminder_energy.enabled:
                view = views.ProfileTimersView(bot, message, interaction_user, user_settings)
                interaction = await message.reply(embed=embed, view=view)
                view.interaction = interaction
                await view.wait()
            else:
                await message.reply(embed=embed)
        if (not user_settings.helper_profile_enabled
            and (user_settings.helper_upgrades_enabled or user_settings.reminder_energy.enabled)):
            add_reaction = True
    return add_reaction