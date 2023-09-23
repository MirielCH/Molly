# clan.py
"""Contains clan commands"""

from typing import Union

import discord
from discord.ext import commands

from database import clans, users, workers
from resources import emojis, exceptions, settings, strings


# --- Commands ---
async def command_clan_power(bot: discord.Bot, ctx: Union[discord.ApplicationContext, commands.Context]) -> None:
    """Clan power command"""
    user_settings: users.User = await users.get_user(ctx.author.id)
    try:
        clan_settings: clans.Clan = await clans.get_clan_by_member_id(ctx.author.id)
    except exceptions.NoDataFoundError:
        msg_error = (
            f'You are either not in a guild or your guild is not registered with me yet.\n'
            f'Use {strings.SLASH_COMMANDS["guild list"]} to do that first.'
        )
        if isinstance(ctx, commands.Context):
            await ctx.reply(msg_error)
        else:
            await ctx.respond(msg_error)
        return
            
    embed = await embed_clan_power(clan_settings)
    if isinstance(ctx, commands.Context):
        await ctx.reply(embed=embed)
    else:
        await ctx.respond(embed=embed)

# --- Embeds ---
async def embed_clan_power(clan_settings: clans.Clan) -> discord.Embed:
    """Workers list embed"""
    embed = discord.Embed(
        color = settings.EMBED_COLOR,
        title = f'{clan_settings.clan_name.upper()} guild power',
    )
    members_top_3_power = {}
    members_outdated = []
    members_not_registered = []
    for member_id in clan_settings.member_ids:
        try:
            member_settings: users.User = await users.get_user(member_id)
            if not member_settings.bot_enabled:
                members_outdated.append(member_id)
                continue
            member_workers = await workers.get_user_workers(member_id)
            worker_levels = {member_worker.worker_name: member_worker.worker_level for member_worker in member_workers}
            workers_power = {}
            for worker_name, worker_level in worker_levels.items():
                worker_power = (
                    ((strings.WORKER_STATS[worker_name]['speed'] + strings.WORKER_STATS[worker_name]['strength']
                        + strings.WORKER_STATS[worker_name]['intelligence']))
                    * (1 + (strings.WORKER_TYPES.index(worker_name) + 1) / 4) * (1 + worker_level / 2.5)
                )
                workers_power[worker_name] = worker_power
            workers_by_power = dict(sorted(workers_power.items(), key=lambda x:x[1], reverse=True))
            top_3_count = 1
            top_3_power = 0
            for worker_name, worker_power in workers_by_power.items():
                if 1 <= top_3_count <= 3: top_3_power += worker_power
                top_3_count += 1
            members_top_3_power[member_id] = top_3_power
        except (exceptions.FirstTimeUserError, exceptions.NoDataFoundError):
            members_not_registered.append(member_id)
    field_top_5_members = ''
    if members_top_3_power:
        members_top_3_power = dict(sorted(members_top_3_power.items(), key=lambda x:x[1], reverse=True))
        loop_count = 1
        for member_id, top_3_power in members_top_3_power.items():
            field_top_5_members = (
                f'{field_top_5_members}\n'
                f'- <@{member_id}> - **{round(top_3_power,2):g}** {emojis.WORKER_POWER}'
            )
            loop_count += 1
            if loop_count > 5: break
    else:
        field_top_5_members = '_No registered worker data found._'
    embed.add_field(
        name = 'Top 5 members',
        value = field_top_5_members.strip(),
        inline = False
    )
    if members_outdated:
        field_members_outdated = ''
        for member_id in members_outdated:
            field_members_outdated = (
                f'{field_members_outdated}\n'
                f'- <@{member_id}>'
            )
        embed.add_field(
            name = 'Members with outdated data',
            value = field_members_outdated.strip(),
            inline = False
        )
    if members_not_registered:
        field_members_not_registered = ''
        for member_id in members_not_registered:
            field_members_not_registered = (
                f'{field_members_not_registered}\n'
                f'- <@{member_id}>'
            )
        embed.add_field(
            name = 'Members not using Molly',
            value = field_members_not_registered.strip(),
            inline = False
        )

    return embed