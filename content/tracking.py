# tracking.py
"""Contains commands related to command tracking"""

from datetime import timedelta
from humanfriendly import format_timespan
from typing import Optional, Union

import discord
from discord.ext import commands

from database import users, tracking
from resources import emojis, functions, exceptions, settings, strings, views


# --- Commands ---
async def command_stats(
    bot: discord.Bot,
    ctx: Union[commands.Context, discord.ApplicationContext, discord.Message],
    timestring: Optional[str] = None,
    user: Optional[discord.User] = None,
) -> None:
    """Lists all stats"""
    if user is None: user = ctx.author
    try:
        user_settings: users.User = await users.get_user(user.id)
    except exceptions.FirstTimeUserError:
        if user == ctx.author:
            raise
        else:
            await functions.reply_or_respond(ctx, 'This user is not registered with this bot.', True)
            return
    if timestring is None:
        embeds = await embeds_stats_overview(ctx, user)
        image = discord.File(settings.IMG_EMBED_WIDTH_LINE, filename='embed_width_line.png')
    else:
        try:
            timestring = await functions.check_timestring(timestring)
        except exceptions.InvalidTimestringError as error:
            msg_error = (
                f'{error}\n'
                f'Supported time codes: `w`, `d`, `h`, `m`, `s`\n\n'
                f'Examples:\n'
                f'{emojis.BP} `30s`\n'
                f'{emojis.BP} `1h30m`\n'
                f'{emojis.BP} `7d`\n'
            )
            await functions.reply_or_respond(ctx, msg_error, True)
            return
        try:
            time_left = await functions.parse_timestring_to_timedelta(timestring)
        except OverflowError as error:
            await ctx.reply(error)
            return
        if time_left.days > 28: time_left = timedelta(days=time_left.days)
        if time_left.days > 365:
            await ctx.reply('The maximum time is 365d, sorry.')
            return
        embed = await embed_stats_timeframe(ctx, user, time_left)
        embeds = (embed,)
        image = None
    if user == ctx.author:
        view = views.StatsView(ctx, user, user_settings)
    else:
        view = None
    if isinstance(ctx, discord.ApplicationContext):
        interaction_message = await ctx.respond(embeds=embeds, view=view, file=image)
    else:
        interaction_message = await ctx.reply(embeds=embeds, view=view, file=image)
    if view is not None:
        view.interaction_message = interaction_message
        await view.wait()


# --- Embeds ---
async def embeds_stats_overview(ctx: commands.Context, user: discord.User) -> discord.Embed:
    """Stats overview embeds"""

    user_settings: users.User = await users.get_user(user.id)
    field_last_1h = await design_field(timedelta(hours=1), user)
    field_last_12h = await design_field(timedelta(hours=12), user)
    field_last_24h = await design_field(timedelta(hours=24), user)
    field_last_7d = await design_field(timedelta(days=7), user)
    field_last_4w = await design_field(timedelta(days=28), user)
    field_last_1y = await design_field(timedelta(days=365), user)
    image_url = 'attachment://embed_width_line.png'
    embed1 = discord.Embed(
        color = settings.EMBED_COLOR,
        title = f'{user.display_name}\'s stats',
        description = '**Command tracking is currently turned off!**' if not user_settings.tracking_enabled else ''
    )
    embed1.add_field(name='Last hour', value=field_last_1h, inline=True)
    embed1.add_field(name='Last 12 hours', value=field_last_12h, inline=True)
    embed1.add_field(name='Last 24 hours', value=field_last_24h, inline=True)
    embed1.set_image(url=image_url)
    embed2 = discord.Embed(
        color = settings.EMBED_COLOR,
    )    
    embed2.add_field(name='Last 7 days', value=field_last_7d, inline=True)
    embed2.add_field(name='Last 4 weeks', value=field_last_4w, inline=True)
    embed2.add_field(name='Last year', value=field_last_1y, inline=True)
    embed2.set_image(url=image_url)
    embed2.set_footer(text='Raid count is not available for data older than 28 days.')
    return (embed1, embed2)


async def embed_stats_timeframe(ctx: commands.Context, user: discord.Member, time_left: timedelta) -> discord.Embed:
    """Stats timeframe embed"""
    user_settings: users.User = await users.get_user(user.id)
    field_content = await design_field(time_left, user)
    embed = discord.Embed(
        color = settings.EMBED_COLOR,
        title = f'{user.display_name}\'s stats',
        description = '**Command tracking is currently turned off!**' if not user_settings.tracking_enabled else ''
    )
    embed.add_field(name=f'Last {format_timespan(time_left)}', value=field_content, inline=False)
    if time_left.days > 28:
        embed.set_footer(text='Raid count is not available for data older than 28 days.')
    return embed


# --- Functions ---
async def design_field(timeframe: timedelta, user: discord.Member) -> str:
    report: tracking.LogReport = await tracking.get_log_report(user.id, timeframe)
    field_content = (
        f'{emojis.BP} **{report.roll_amount:,} rolls**'
    )
    for worker_name, worker_amount in report.workers.items():
        if worker_name not in strings.WORKER_TYPES_TRACKED: continue
        worker_emoji = getattr(emojis, f'WORKER_{worker_name}_A'.upper(), emojis.WARNING)
        detail_emoji = emojis.DETAIL if worker_name == list(report.workers.keys())[-1] else emojis.DETAIL2
        try:
            percentage = round(worker_amount / report.roll_amount * 100, 2)
        except ZeroDivisionError:
            percentage = 0
        field_content = (
            f'{field_content}\n'
            f'{detail_emoji} {worker_emoji} **{worker_amount:,}** ({percentage:g}%)'
        )
    raid_amount = f'{report.raid_amount:,} raids' if report.raid_amount != -1 else 'Raids'
    field_content = (
        f'{field_content}\n'
        f'{emojis.BP} **{raid_amount}**\n'
        f'{emojis.DETAIL2} {emojis.RAID_POINT} gained: **{report.raid_points_gained:,}**\n'
        f'{emojis.DETAIL2} {emojis.RAID_POINT} lost: **{report.raid_points_lost:,}**\n'
        f'{emojis.DETAIL} {emojis.RAID_POINT} total: **{report.raid_points_gained - report.raid_points_lost:,}**'
    )
    return field_content