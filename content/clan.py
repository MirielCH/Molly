# clan.py
"""Contains clan commands"""

from typing import Optional, Tuple, Union

import discord
from discord.ext import commands

from database import clans, users, upgrades, workers
from resources import emojis, exceptions, settings, strings, views


# --- Commands ---
async def command_clan_members(bot: discord.Bot, ctx: Union[discord.ApplicationContext, commands.Context],
                               current_view: int) -> None:
    """Clan list command"""
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
    view = views.ClanMembersView(ctx, clan_settings, current_view, embeds_clan_members)
    embeds = await embeds_clan_members(clan_settings, current_view=current_view)
    image = None
    if len(embeds) > 1:
        image = discord.File(settings.IMG_EMBED_WIDTH_LINE, filename='embed_width_line.png')
    if isinstance(ctx, discord.ApplicationContext):
        interaction = await ctx.respond(embeds=embeds, view=view, file=image)
    else:
        interaction = await ctx.reply(embeds=embeds, view=view, file=image)
    view.interaction_message = interaction
    await view.wait()
    

# --- Embeds ---
async def embeds_clan_members(clan_settings: clans.Clan, current_view: Optional[int] = 0,
                              sort_key: Optional[str] = None) -> Tuple[discord.Embed]:
    """Clan members list embed"""
    embeds = []
    members = {}
    members_disabled = []
    members_no_upgrades = []
    members_no_workers = []
    members_not_registered = []
    guild_seals_contributed_total = guild_seals_inventory_total = 0
    for clan_member in clan_settings.members:
        guild_seals_contributed_total += clan_member.guild_seals_contributed
        try:
            member_settings: users.User = await users.get_user(clan_member.user_id)
            guild_seals_inventory_total += member_settings.inventory.guild_seal
            if not member_settings.bot_enabled:
                members_disabled.append(clan_member)
                continue
            try:
                teamfarm_life_upgrade = await upgrades.get_upgrade(clan_member.user_id, 'teamfarm life')
                teamfarm_life_level = teamfarm_life_upgrade.level
            except exceptions.NoDataFoundError:
                members_no_upgrades.append(clan_member)
                continue
            try:
                member_workers = await workers.get_user_workers(clan_member.user_id)
            except exceptions.NoDataFoundError:
                members_no_workers.append(clan_member)
                continue
            worker_levels = {member_worker.worker_name: member_worker.worker_level for member_worker in member_workers}
            workers_power = {}
            for worker_name, worker_level in worker_levels.items():
                worker_power = (
                    ((strings.WORKER_STATS[worker_name]['speed'] + strings.WORKER_STATS[worker_name]['strength']
                        + strings.WORKER_STATS[worker_name]['intelligence']))
                    * (1 + (strings.WORKER_STATS[worker_name]['tier']) / 2.5) * (1 + worker_level / 1.25)
                )
                workers_power[worker_name] = worker_power
            workers_by_power = dict(sorted(workers_power.items(), key=lambda x:x[1], reverse=True))
            top_3_count = 1
            top_3_power = 0
            for worker_name, worker_power in workers_by_power.items():
                if 1 <= top_3_count <= 3: top_3_power += worker_power
                top_3_count += 1
            members[clan_member.user_id] = {
                'top_3_power': top_3_power,
                'guild_seals_inventory': member_settings.inventory.guild_seal,
                'guild_seals_contributed': clan_member.guild_seals_contributed,
                'teamfarm_life': teamfarm_life_level
            }
        except exceptions.FirstTimeUserError:
            members_not_registered.append(clan_member)
    field_no = 1
    fields_members = {field_no: ''}
    if current_view == 0:
        current_view_name = 'Top 3 power'
        if sort_key is None: sort_key = 'top_3_power'
        overview = None
    if current_view == 1:
        current_view_name = 'Guild seals'
        if sort_key is None: sort_key = 'guild_seals_contributed'
        unlocked_guild_buff = 'No buff'
        next_threshold = 5
        for index, threshold in enumerate(strings.GUILD_BUFF_THRESHOLDS):
            if guild_seals_contributed_total >= threshold:
                unlocked_guild_buff = f'Guild buff {strings.NUMBERS_INTEGER_ROMAN[index + 1].upper()}'
                if threshold == strings.GUILD_BUFF_THRESHOLDS[-1]:
                    next_threshold = -1
                else:
                    next_threshold = strings.GUILD_BUFF_THRESHOLDS[index + 1]
            else:
                break
        overview = (
            f'**`{guild_seals_contributed_total:,}`** {emojis.GUILD_SEAL_CONTRIBUTED} contributed (**{unlocked_guild_buff}**)'
        )
        if next_threshold > -1:
            overview = (
                f'{overview}\n'
                f'{emojis.DETAIL} Next buff unlocked at `{next_threshold:,}` {emojis.GUILD_SEAL}'
            )
        else:
            overview = (
                f'{overview}\n'
                f'{emojis.DETAIL} All buffs unlocked!'
            )
        overview = (
            f'{overview}\n'
            f'**`{guild_seals_inventory_total:,}`** {emojis.GUILD_SEAL_INVENTORY} found in inventories'
        )
    embed = discord.Embed(
        color = settings.EMBED_COLOR,
        title = f'{clan_settings.clan_name.upper()} - {current_view_name}',
    )
    if overview is not None:
        embed.add_field(name='Overview', value=overview)
    if members:
        members = dict(sorted(members.items(), key=lambda x:x[1][sort_key], reverse=True))
        for member_id, member_data in members.items():
            index = (
                f'{list(members.keys()).index(member_id) + 1}.'.rjust(3,'0')
            )
            if current_view == 0:
                member_power_str = f' {round(member_data["top_3_power"],2):,g}'.rjust(8)
                member_teamfarm_life_level_str = f' {member_data["teamfarm_life"]}'
                field_value = (
                    f'`{index}`| **`{member_power_str}`**💥 `Lv{member_teamfarm_life_level_str}`{emojis.IDLONS} <@{member_id}>'
                )
            elif current_view == 1:
                guild_seals_inventory_str = f' {member_data["guild_seals_inventory"]:,}'.rjust(5)
                guild_seals_contributed_str = f' {member_data["guild_seals_contributed"]:,}'.rjust(5)
                field_value = (
                    f'`{index}`| **`{guild_seals_contributed_str}`**{emojis.GUILD_SEAL_CONTRIBUTED} '
                    f'**`{guild_seals_inventory_str}`**{emojis.GUILD_SEAL_INVENTORY} <@{member_id}>'
                )
            if len(fields_members[field_no]) + len(field_value) > 1020:
                field_no += 1
                fields_members[field_no] = ''
            fields_members[field_no] = f'{fields_members[field_no]}\n{field_value}'
    else:
        embed.add_field(name='Members', value='_No registered members found._', inline=False)
    for field_no, field in fields_members.items():
        if field_no == 6:
            embeds.append(embed)
            embed = discord.Embed(color = settings.EMBED_COLOR)
        field_name = f'Members ({field_no})' if field_no > 1 else 'Members'
        embed.add_field(name=field_name, value=field.strip(), inline=False)
    embeds.append(embed)
    if members_not_registered or members_no_upgrades or members_no_workers or members_disabled:
        embed = discord.Embed(color=settings.EMBED_COLOR)
    if members_disabled:
        field_members_disabled = ''
        for clan_member in members_disabled:
            field_members_disabled = (
                f'{field_members_disabled}\n'
                f'- <@{clan_member.user_id}>'
            )
            if len(field_members_disabled) >= 900:
                field_members_disabled = (
                    f'{field_members_disabled}\n'
                    f'- ...'
                )
                break
        embed.add_field(
            name = 'Members who have Molly disabled',
            value = (
                f'{field_members_disabled.strip()}'
            ),
            inline = False
        )
    if members_no_workers:
        field_members_no_workers = ''
        for clan_member in members_no_workers:
            field_members_no_workers = (
                f'{field_members_no_workers}\n'
                f'- <@{clan_member.user_id}>'
            )
            if len(field_members_no_workers) >= 900:
                field_members_no_workers = (
                    f'{field_members_no_workers}\n'
                    f'- ...'
                )
                break
        embed.add_field(
            name = 'Members with missing worker data',
            value = (
                f'{field_members_no_workers.strip()}'
            ),
            inline = False
        )
    if members_no_upgrades:
        field_members_no_upgrades = ''
        for clan_member in members_no_upgrades:
            field_members_no_upgrades = (
                f'{field_members_no_upgrades}\n'
                f'- <@{clan_member.user_id}>'
            )
            if len(field_members_no_upgrades) >= 900:
                field_members_no_upgrades = (
                    f'{field_members_no_upgrades}\n'
                    f'- ...'
                )
                break
        embed.add_field(
            name = 'Members with missing upgrades data',
            value = (
                f'{field_members_no_upgrades.strip()}'
            ),
            inline = False
        )
    if members_not_registered:
        field_members_not_registered = ''
        for clan_member in members_not_registered:
            field_members_not_registered = (
                f'{field_members_not_registered}\n'
                f'- <@{clan_member.user_id}>'
            )
            if len(field_members_not_registered) >= 900:
                field_members_not_registered = (
                    f'{field_members_not_registered}\n'
                    f'- ...'
                )
                break
        embed.add_field(
            name = 'Members not registered with Molly',
            value = (
                f'{field_members_not_registered.strip()}'
            ),
            inline = False
        )
    if current_view == 0:
        field_legend = (
            f'💥 Top 3 power\n'
            f'{emojis.IDLONS} Teamfarm life upgrade level'
        )
    elif current_view == 1:
        field_legend = (
            f'{emojis.GUILD_SEAL_CONTRIBUTED} Guild seals contributed this week\n'
            f'{emojis.GUILD_SEAL_INVENTORY} Guild seals in inventory'
        )
    embed.add_field(
        name = 'Legend',
        value = field_legend,
        inline = False
    )
    if members_not_registered or members_no_upgrades or members_disabled:
        embeds.append(embed)

    if len(embeds) > 1:
        image_url = 'attachment://embed_width_line.png'
        for embed in embeds:
            embed.set_image(url=image_url)

    return embeds