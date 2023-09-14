# workers.py
"""Contains worker commands"""

from typing import List, Union

import discord
from discord.ext import commands

from database import users, workers
from resources import emojis, exceptions, functions, settings, strings


# --- Commands ---
async def command_workers_list(bot: discord.Bot, ctx: Union[discord.ApplicationContext, commands.Context]) -> None:
    """Workers list command"""
    user_settings: users.User = await users.get_user(ctx.author.id)
    start_tracking = (
        f'To start tracking your workers do the following:\n'
        f'{emojis.BP} Use {await functions.get_bot_slash_command(bot, "on")} to enable me\n'
        f'{emojis.BP} Use {await functions.get_game_command(user_settings, "worker stats")} to start tracking your workers'
    )
    if not user_settings.bot_enabled:
        msg_error = (
            f'I am currently turned off.\n'
            f'{start_tracking}'
        )
        if isinstance(ctx, commands.Context):
            await ctx.reply(msg_error)
        else:
            await ctx.respond(msg_error)
        return
    try:
        user_workers = await workers.get_user_workers(ctx.author.id)
    except exceptions.NoDataFoundError:
        msg_error = (
            f'Looks like I don\'t know your workers yet.\n'
            f'{start_tracking}'
        )
        if isinstance(ctx, commands.Context):
            await ctx.reply(msg_error)
        else:
            await ctx.respond(msg_error)
        return
    embed = await embed_workers_list(user_workers)
    if isinstance(ctx, commands.Context):
        await ctx.reply(embed=embed)
    else:
        await ctx.respond(embed=embed)

# --- Embeds ---
async def embed_workers_list(user_workers: List[workers.UserWorker]) -> discord.Embed:
    """Workers list embed"""
    worker_levels = {user_worker.worker_name: user_worker.worker_level for user_worker in user_workers}
    workers_power = {}
    for worker_name, worker_level in worker_levels.items():
        worker_power = (
            ((strings.WORKER_STATS[worker_name]['speed'] + strings.WORKER_STATS[worker_name]['strength']
                + strings.WORKER_STATS[worker_name]['intelligence']))
            * (1 + (strings.WORKER_TYPES.index(worker_name) + 1) / 4) * (1 + worker_level / 1.5) * 0.8
        )
        workers_power[worker_name] = worker_power
    workers_by_type = {}
    for worker_type in strings.WORKER_TYPES:
        if worker_type in workers_power:
            workers_by_type[worker_type] = workers_power[worker_type]
    workers_by_power = dict(sorted(workers_power.items(), key=lambda x:x[1], reverse=True))
    field_workers_by_power = field_workers_by_type = ''
    top_3_count = 1
    top_3_power = 0
    for worker_name, worker_power in workers_by_type.items():
        worker_emoji = getattr(emojis, f'WORKER_{worker_name}_A'.upper(), emojis.WARNING)
        worker_power = round(worker_power, 2)
        field_workers_by_type = (
            f'{field_workers_by_type}\n'
            f'{worker_emoji} - {worker_power:,g} {emojis.WORKER_POWER}'
        )
    for worker_name, worker_power in workers_by_power.items():
        worker_emoji = getattr(emojis, f'WORKER_{worker_name}_A'.upper(), emojis.WARNING)
        if 1 <= top_3_count <= 3:
            top_3_power += worker_power
        top_3_count += 1
        worker_power = round(worker_power, 2)
        field_workers_by_power = (
            f'{field_workers_by_power}\n'
            f'{worker_emoji} - {worker_power:,g} {emojis.WORKER_POWER}'
        )
    embed = discord.Embed(
        title = 'Worker power',
        description = f'Top 3 power: **{round(top_3_power, 2)}** {emojis.WORKER_POWER}',
        color = settings.EMBED_COLOR,
    )
    embed.add_field(
        name = 'By type',
        value = field_workers_by_type.strip(),
        inline = True
    )
    embed.add_field(
        name = 'By power',
        value = field_workers_by_power.strip(),
        inline = True
    )
    return embed