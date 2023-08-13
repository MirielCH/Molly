# reminders_lists.py
"""Contains reminder list commands"""

from datetime import datetime, timedelta, timezone
from typing import List, Optional, Union

import discord
from discord import utils
from discord.ext import commands
from humanfriendly import format_timespan

from database import clans, reminders, users
from resources import emojis, functions, exceptions, settings, strings, views


# -- Commands ---
async def command_list(
    bot: discord.Bot,
    ctx: Union[commands.Context, discord.ApplicationContext, discord.Message],
    user: Optional[discord.User] = None
) -> None:
    """Lists all active reminders"""
    user = user if user is not None else ctx.author
    try:
        user_settings: users.User = await users.get_user(user.id)
    except exceptions.FirstTimeUserError:
        if user == ctx.author:
            raise
        else:
            await functions.reply_or_respond(ctx, 'This user is not registered with me.', True)
        return
    try:
        custom_reminders = list(await reminders.get_active_user_reminders(user.id, 'custom'))
    except exceptions.NoDataFoundError:
        custom_reminders = []
    embed = await embed_reminders_list(bot, user, user_settings, custom_reminders)
    view = views.RemindersListView(bot, ctx, user, user_settings, custom_reminders, embed_reminders_list)
    if isinstance(ctx, discord.ApplicationContext):
        interaction_message = await ctx.respond(embed=embed, view=view)
    else:
        interaction_message = await ctx.reply(embed=embed, view=view)
    view.interaction_message = interaction_message
    await view.wait()


# -- Embeds ---
async def embed_reminders_list(bot: discord.Bot, user: discord.User, user_settings: users.User,
                               custom_reminders: List[reminders.Reminder]) -> discord.Embed:
    """Embed with active reminders"""
    try:
        user_reminders = list(await reminders.get_active_user_reminders(user.id))
    except exceptions.NoDataFoundError:
        user_reminders = []
    try:
        clan_settings: clans.Clan = await clans.get_clan_by_member_id(user.id)
    except exceptions.NoDataFoundError:
        clan_settings = None
    clan_reminder = None
    if clan_settings is not None:
        try:
            clan_reminder = await reminders.get_clan_reminder(clan_settings.clan_name)
        except exceptions.NoDataFoundError:
            pass
    clan_reminder_enabled = getattr(clan_settings, 'reminder_enabled', False)
    current_time = utils.utcnow()
    claim_reminder = daily_reminder = vote_reminder = None
    for reminder in user_reminders:
        if reminder.activity == 'daily':
            daily_reminder = reminder
        elif reminder.activity == 'claim':
            claim_reminder = reminder
        elif reminder.activity == 'vote':
            claim_reminder = reminder

    last_claim_time_timestamp = farms_full_in_timestamp = 'Never'
    time_produced_timespan = 'None'
    if user_settings.reminder_claim.enabled and user_settings.last_claim_time > datetime(year=1970, month=1, day=1, tzinfo=timezone.utc):
        time_since_last_claim = current_time - user_settings.last_claim_time
        time_produced = time_since_last_claim + user_settings.time_speeders_used * timedelta(hours=2)
        if time_produced >= timedelta(hours=24): time_produced = timedelta(hours=24)
        farms_full_in = user_settings.last_claim_time + (timedelta(hours=24) - user_settings.time_speeders_used * timedelta(hours=2))
        last_claim_time_timestamp = utils.format_dt(user_settings.last_claim_time, 'R')
        time_produced_timespan = f'`{format_timespan(time_produced - timedelta(microseconds=time_produced.microseconds))}`'
        if time_produced >= timedelta(hours=24): time_produced_timespan = f'{emojis.WARNING}`{time_produced_timespan}`'
        if claim_reminder is not None:
            claim_reminder_end_time = utils.format_dt(claim_reminder.end_time, 'R')
        else:
            claim_reminder_end_time = ''
        farms_full_in_timestamp = utils.format_dt(farms_full_in, 'R')
        if farms_full_in <= current_time:
            farms_full_in_timestamp = f'{emojis.WARNING}{farms_full_in_timestamp}'
    if daily_reminder is not None:
        daily_reminder_end_time = utils.format_dt(daily_reminder.end_time, 'R')
    else:
        daily_reminder_end_time = ''
    if clan_reminder is not None:
        clan_reminder_end_time = utils.format_dt(clan_reminder.end_time, 'R')
    else:
        clan_reminder_end_time = ''
    claim_reminder_emoji = emojis.ENABLED_LARGE if claim_reminder is None else emojis.COOLDOWN
    claim_reminder_text = '`Ready!`' if claim_reminder is None else claim_reminder_end_time
    daily_reminder_emoji = emojis.ENABLED_LARGE if daily_reminder is None else emojis.COOLDOWN
    daily_reminder_text = '`Ready!`' if daily_reminder is None else daily_reminder_end_time
    vote_reminder_emoji = emojis.ENABLED_LARGE if vote_reminder is None else emojis.COOLDOWN
    #vote_reminder_text = '`Ready`' if vote_reminder is None else vote_reminder_end_time
    clan_reminder_emoji = emojis.ENABLED_LARGE if clan_reminder is None else emojis.COOLDOWN
    clan_reminder_text = '`Ready!`' if clan_reminder is None else clan_reminder_end_time
    embed = discord.Embed(
        color = settings.EMBED_COLOR,
        title = f'{user.display_name}\'s commands',
    )
    if user_settings.reminder_claim.enabled:
        embed.add_field(
            name=f'{claim_reminder_emoji} {strings.SLASH_COMMANDS["claim"]} {claim_reminder_text}',
            value=(
                f'{emojis.DETAIL2} **Last claim**: {last_claim_time_timestamp}\n'
                f'{emojis.DETAIL2} **Time speeders used**: `{user_settings.time_speeders_used}`\n'
                f'{emojis.DETAIL2} **Farm production time**: {time_produced_timespan}\n'
                f'{emojis.DETAIL} **Farms at full capacity**: {farms_full_in_timestamp}\n'
            ).strip(),
            inline=False
        )
    if user_settings.reminder_daily.enabled:
        embed.add_field(
            name=f'{daily_reminder_emoji} {strings.SLASH_COMMANDS["daily"]} {daily_reminder_text}',
            value=f'{emojis.DETAIL} _The daily rewards reset at midnight UTC._',
            inline=False
        )
    """
    if user_settings.reminder_vote.enabled:
        embed.add_field(
            name=f'{vote_reminder_emoji} {strings.SLASH_COMMANDS["vote"]} {vote_reminder_active}',
            value=f'{emojis.DETAIL} _You can vote every 12 hours._',
            inline=False
        )
    """
    if clan_reminder_enabled:
        embed.add_field(
            name=f'{clan_reminder_emoji} {strings.SLASH_COMMANDS["teamraid"]} {clan_reminder_text}',
            value=(
                f'{emojis.DETAIL2} **Guild name**: `{clan_settings.clan_name.upper()}`\n'
                f'{emojis.DETAIL} **Guild channel**: <#{clan_settings.reminder_channel_id}>\n'
            ),
            inline=False
        )
    if custom_reminders:
        field_custom_reminders = ''
        for reminder in custom_reminders:
            custom_id = f'0{reminder.custom_id}' if reminder.custom_id <= 9 else reminder.custom_id
            emoji = emojis.DETAIL if reminder == custom_reminders[-1] else emojis.DETAIL2
            field_custom_reminders = (
                f'{field_custom_reminders}\n'
                f'{emoji} **{custom_id}** • {utils.format_dt(reminder.end_time, "R")} • {reminder.message}'
            )
        embed.add_field(name='Custom reminders', value=field_custom_reminders.strip(), inline=False)
    return embed