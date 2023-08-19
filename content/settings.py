# settings.py
"""Contains settings commands"""

import asyncio
from datetime import datetime, timezone
import re
from typing import List, Optional

import discord
from discord import utils

from database import clans, guilds, reminders, tracking, users
from resources import emojis, exceptions, functions, settings, strings, views


# --- Commands ---
async def command_on(bot: discord.Bot, ctx: discord.ApplicationContext) -> None:
    """On command"""
    first_time_user = False
    try:
        user_settings: users.User = await users.get_user(ctx.author.id)
        if user_settings.bot_enabled:
            await ctx.respond(f'**{ctx.author.display_name}**, I\'m already turned on.', ephemeral=True)
            return
    except exceptions.FirstTimeUserError:
        user_settings = await users.insert_user(ctx.author.id)
        first_time_user = True
    if not user_settings.bot_enabled: await user_settings.update(bot_enabled=True)
    if not user_settings.bot_enabled:
        await ctx.respond(strings.MSG_ERROR, ephemeral=True)
        return
    if not first_time_user:
        answer = f'Yeehaw! Welcome back **{ctx.author.display_name}**!'
        await ctx.respond(answer)
    else:
        field_first = (
            f'Please do the following to properly use my features:\n'
            f'{emojis.BP} Use {await functions.get_game_command(user_settings, "donate")} to set your donor tier\n'
            f'{emojis.BP} Use {await functions.get_game_command(user_settings, "worker stats")} to update your workers\n'
            f'{emojis.BP} Use {await functions.get_game_command(user_settings, "upgrades")} to update your upgrades\n'
            f'{emojis.BP} Use {await functions.get_game_command(user_settings, "profile")} to update your idlucks\n'
        )
        field_tracking = (
            f'I track your IDLE FARM workers, upgrades and count your rolls and raid points. Check '
            f'{await functions.get_bot_slash_command(bot, "stats")} to see your rolls and raids.\n'
            f'**__No personal data is processed or stored in any way!__**\n'
            f'You can turn off features you don\'t want in the user settings.\n\n'
        )
        field_settings = (
            f'To view and change your settings, click the button below or use '
            f'{await functions.get_bot_slash_command(bot, "settings user")}.'
        )
        file_name = 'logo.png'
        img_logo = discord.File(settings.IMG_LOGO, filename=file_name)
        image_url = f'attachment://{file_name}'
        embed = discord.Embed(
            title = f'Yeehaw {ctx.author.display_name}!',
            description = (
                f'I am here to help you playing IDLE FARM!\n'
                f'Have a look at {await functions.get_bot_slash_command(bot, "help")} for a list of my commands.'
            ),
            color =  settings.EMBED_COLOR,
        )
        embed.add_field(name='First things first', value=field_first, inline=False)
        embed.add_field(name='Settings', value=field_settings, inline=False)
        embed.add_field(name='Command tracking', value=field_tracking, inline=False)
        embed.set_thumbnail(url=image_url)
        view = views.OneButtonView(ctx, discord.ButtonStyle.blurple, 'pressed', '➜ Settings')
        interaction = await ctx.respond(embed=embed, file=img_logo, view=view)
        view.interaction_message = interaction
        await view.wait()
        if view.value == 'pressed':
            await functions.edit_interaction(interaction, view=None)
            await command_settings_user(bot, ctx)


async def command_off(bot: discord.Bot, ctx: discord.ApplicationContext) -> None:
    """Off command"""
    user: users.User = await users.get_user(ctx.author.id)
    if not user.bot_enabled:
        await ctx.respond(f'**{ctx.author.display_name}**, I\'m already turned off.', ephemeral=True)
        return
    answer = (
        f'**{ctx.author.display_name}**, turning me off will disable me completely. It will also delete all of your active '
        f'reminders.\n'
        f'Are you sure?'
    )
    view = views.ConfirmCancelView(ctx, styles=[discord.ButtonStyle.red, discord.ButtonStyle.grey])
    interaction = await ctx.respond(answer, view=view)
    view.interaction_message = interaction
    await view.wait()
    if view.value is None:
        await functions.edit_interaction(
            interaction, content=f'**{ctx.author.display_name}**, you left me standing here like an idiot.', view=None)
    elif view.value == 'confirm':
        await user.update(bot_enabled=False)
        try:
            active_reminders = await reminders.get_active_user_reminders(ctx.author.id)
            for reminder in active_reminders:
                await reminder.delete()
        except exceptions.NoDataFoundError:
            pass
        if not user.bot_enabled:
            answer = (
                f'**{ctx.author.display_name}**, I\'m now turned off.\n'
                f'All active reminders were deleted.\n'
                f'Yeehaw! {emojis.LOGO}'
            )
            await functions.edit_interaction(interaction, content=answer, view=None)
        else:
            await ctx.followup.send(strings.MSG_ERROR)
            return
    else:
        await functions.edit_interaction(interaction, content='Aborted.', view=None)


async def command_purge_data(bot: discord.Bot, ctx: discord.ApplicationContext) -> None:
    """Purge data command"""
    user_settings: users.User = await users.get_user(ctx.author.id)
    answer_aborted = f'**{ctx.author.display_name}**, phew, was worried there for a second.'
    answer_timeout = f'**{ctx.author.display_name}**, you didn\'t answer in time.'
    answer = (
        f'{emojis.WARNING} **{ctx.author.display_name}**, this will purge your user data from Molly **completely** {emojis.WARNING}\n\n'
        f'This includes the following:\n'
        f'{emojis.BP} Your reminders\n'
        f'{emojis.BP} Your workers\n'
        f'{emojis.BP} Your upgrades\n'
        f'{emojis.BP} Your complete tracking history\n'
        f'{emojis.BP} And finally, your user settings\n\n'
        f'**There is no coming back from this**.\n'
        f'You will of course be able to start using Molly again, but all of your data will start '
        f'from scratch.\n'
        f'Are you **SURE**?'
    )
    view = views.ConfirmCancelView(ctx, styles=[discord.ButtonStyle.red, discord.ButtonStyle.green])
    interaction = await ctx.respond(answer, view=view)
    view.interaction_message = interaction
    await view.wait()
    if view.value is None:
        await functions.edit_interaction(
            interaction, content=answer_timeout, view=None
        )
    elif view.value == 'confirm':
        await functions.edit_interaction(interaction, view=None)
        answer = (
            f'{emojis.WARNING} **{ctx.author.display_name}**, just a friendly final warning {emojis.WARNING}\n'
            f'**ARE YOU SURE?**'
        )
        view = views.ConfirmCancelView(ctx, styles=[discord.ButtonStyle.red, discord.ButtonStyle.green])
        interaction = await ctx.respond(answer, view=view)
        view.interaction_message = interaction
        await view.wait()
        if view.value is None:
            await functions.edit_interaction(
                interaction, content=answer_timeout, view=None
            )
        elif view.value == 'confirm':
            cur = settings.DATABASE.cursor()
            await functions.edit_interaction(
                interaction, content='Purging user settings...',
                view=None
            )
            cur.execute('DELETE FROM users WHERE user_id=?', (ctx.author.id,))
            await asyncio.sleep(1)
            await functions.edit_interaction(
                interaction, content='Purging reminders...',
                view=None
            )
            cur.execute('DELETE FROM user_reminders WHERE user_id=?', (ctx.author.id,))
            await asyncio.sleep(1)
            await functions.edit_interaction(
                interaction, content='Purging worker data...',
                view=None
            )
            cur.execute('DELETE FROM user_workers WHERE user_id=?', (ctx.author.id,))
            await asyncio.sleep(1)
            await functions.edit_interaction(
                interaction, content='Purging upgrade data...',
                view=None
            )
            cur.execute('DELETE FROM user_upgrades WHERE user_id=?', (ctx.author.id,))
            await asyncio.sleep(1)
            await functions.edit_interaction(
                interaction, content='Purging tracking data... (this can take a while)',
                view=None
            )
            try:
                log_entries =  await tracking.get_all_log_entries(ctx.author.id)
            except exceptions.NoDataFoundError:
                log_entries = []
            for log_entry in log_entries:
                await log_entry.delete()
                await asyncio.sleep(0.01)
            await asyncio.sleep(1)
            await functions.edit_interaction(
                interaction,
                content=(
                    f'{emojis.ENABLED} **{ctx.author.display_name}**, you are now gone and forgotten. '
                    f'Thanks for using me! Yeehaw! {emojis.LOGO}'
                ),
                view=None
            )   
        else:
            await functions.edit_interaction(
                interaction, content=answer_aborted, view=None
            )
    else:
        await functions.edit_interaction(
            interaction, content=answer_aborted, view=None
        )


async def command_settings_clan(bot: discord.Bot, ctx: discord.ApplicationContext,
                                switch_view: Optional[discord.ui.View] = None) -> None:
    """Clan settings command"""
    commands_settings = {
        'Guild': command_settings_clan,
        'Helpers': command_settings_helpers,
        'Reminders': command_settings_reminders,
        'Reminder messages': command_settings_messages,
        'User': command_settings_user,
    }
    user_settings: users.User = await users.get_user(ctx.author.id)
    clan_settings = interaction = None
    if switch_view is not None:
        clan_settings = getattr(switch_view, 'clan_settings', None)
        interaction = getattr(switch_view, 'interaction', None)
    if clan_settings is None:
        try:
            clan_settings: clans.Clan = await clans.get_clan_by_member_id(ctx.author.id)
        except exceptions.NoDataFoundError:
            await ctx.respond(
                f'Your guild is not registered with me yet. Use {strings.SLASH_COMMANDS["guild list"]} '
                f'to do that first.',
                ephemeral=True
            )
            return
    if switch_view is not None: switch_view.stop()
    view = views.SettingsClanView(ctx, bot, clan_settings, user_settings, embed_settings_clan, commands_settings)
    embed = await embed_settings_clan(bot, ctx, clan_settings)
    if interaction is None:
        interaction = await ctx.respond(embed=embed, view=view)
    else:
        await functions.edit_interaction(interaction, embed=embed, view=view)
    view.interaction = interaction
    await view.wait()


async def command_settings_helpers(bot: discord.Bot, ctx: discord.ApplicationContext,
                                   switch_view: Optional[discord.ui.View] = None) -> None:
    """Helper settings command"""
    commands_settings = {
        'Guild': command_settings_clan,
        'Helpers': command_settings_helpers,
        'Reminders': command_settings_reminders,
        'Reminder messages': command_settings_messages,
        'User': command_settings_user,
    }
    user_settings = interaction = None
    if switch_view is not None:
        user_settings = getattr(switch_view, 'user_settings', None)
        interaction = getattr(switch_view, 'interaction', None)
        switch_view.stop()
    if user_settings is None:
        user_settings: users.User = await users.get_user(ctx.author.id)
    view = views.SettingsHelpersView(ctx, bot, user_settings, embed_settings_helpers, commands_settings)
    embed = await embed_settings_helpers(bot, ctx, user_settings)
    if interaction is None:
        interaction = await ctx.respond(embed=embed, view=view)
    else:
        await functions.edit_interaction(interaction, embed=embed, view=view)
    view.interaction = interaction
    await view.wait()

    
async def command_settings_messages(bot: discord.Bot, ctx: discord.ApplicationContext,
                                    switch_view: Optional[discord.ui.View] = None) -> None:
    """Reminder message settings command"""
    commands_settings = {
        'Guild': command_settings_clan,
        'Helpers': command_settings_helpers,
        'Reminders': command_settings_reminders,
        'Reminder messages': command_settings_messages,
        'User': command_settings_user,
    }
    user_settings = interaction = None
    if switch_view is not None:
        user_settings = getattr(switch_view, 'user_settings', None)
        interaction = getattr(switch_view, 'interaction', None)
        switch_view.stop()
    if user_settings is None:
        user_settings: users.User = await users.get_user(ctx.author.id)
    view = views.SettingsMessagesView(ctx, bot, user_settings, embed_settings_messages, commands_settings, 'all')
    embed = await embed_settings_messages(bot, ctx, user_settings, 'all')
    if interaction is None:
        interaction = await ctx.respond(embed=embed, view=view)
    else:
        await functions.edit_interaction(interaction, embed=embed, view=view)
    view.interaction = interaction
    await view.wait()


async def command_settings_reminders(bot: discord.Bot, ctx: discord.ApplicationContext,
                                     switch_view: Optional[discord.ui.View] = None) -> None:
    """Reminder settings command"""
    commands_settings = {
        'Guild': command_settings_clan,
        'Helpers': command_settings_helpers,
        'Reminders': command_settings_reminders,
        'Reminder messages': command_settings_messages,
        'User': command_settings_user,
    }
    user_settings = interaction = None
    if switch_view is not None:
        user_settings = getattr(switch_view, 'user_settings', None)
        interaction = getattr(switch_view, 'interaction', None)
        switch_view.stop()
    if user_settings is None:
        user_settings: users.User = await users.get_user(ctx.author.id)
    view = views.SettingsRemindersView(ctx, bot, user_settings, embed_settings_reminders, commands_settings)
    embed = await embed_settings_reminders(bot, ctx, user_settings)
    if interaction is None:
        interaction = await ctx.respond(embed=embed, view=view)
    else:
        await functions.edit_interaction(interaction, embed=embed, view=view)
    view.interaction = interaction
    await view.wait()


async def command_settings_server(bot: discord.Bot, ctx: discord.ApplicationContext) -> None:
    """Server settings command"""
    guild_settings: guilds.Guild = await guilds.get_guild(ctx.guild.id)
    view = views.SettingsServerView(ctx, bot, guild_settings, embed_settings_server)
    embed = await embed_settings_server(bot, ctx, guild_settings)
    interaction = await ctx.respond(embed=embed, view=view)
    view.interaction = interaction
    await view.wait()


async def command_settings_user(bot: discord.Bot, ctx: discord.ApplicationContext,
                                switch_view: Optional[discord.ui.View] = None) -> None:
    """User settings command"""
    commands_settings = {
        'Guild': command_settings_clan,
        'Helpers': command_settings_helpers,
        'Reminders': command_settings_reminders,
        'Reminder messages': command_settings_messages,
        'User': command_settings_user,
    }
    user_settings = interaction = None
    if switch_view is not None:
        user_settings = getattr(switch_view, 'user_settings', None)
        interaction = getattr(switch_view, 'interaction', None)
        switch_view.stop()
    if user_settings is None:
        user_settings: users.User = await users.get_user(ctx.author.id)
    view = views.SettingsUserView(ctx, bot, user_settings, embed_settings_user, commands_settings)
    embed = await embed_settings_user(bot, ctx, user_settings)
    if interaction is None:
        interaction = await ctx.respond(embed=embed, view=view)
    else:
        await functions.edit_interaction(interaction, embed=embed, view=view)
    view.interaction = interaction
    await view.wait()


# --- Embeds ---
async def embed_settings_clan(bot: discord.Bot, ctx: discord.ApplicationContext, clan_settings: clans.Clan) -> discord.Embed:
    """Clan settings embed"""
    teamraid_enabled = await functions.bool_to_text(clan_settings.helper_teamraid_enabled)
    reminder_enabled = await functions.bool_to_text(clan_settings.reminder_enabled)
    if clan_settings.reminder_channel_id is not None:
        clan_channel = f'<#{clan_settings.reminder_channel_id}>'
    else:
        clan_channel = '`Not set`'
    if clan_settings.reminder_role_id is not None:
        clan_role = f'<@&{clan_settings.reminder_role_id}>'
    else:
        clan_role = '`Not set`'

    overview = (
        f'{emojis.BP} **Name**: `{clan_settings.clan_name}`\n'
        f'{emojis.BP} **Owner**: <@{clan_settings.leader_id}>\n'
    )
    reminder = (
        f'{emojis.BP} **Reminder**: {reminder_enabled}\n'
        f'{emojis.BP} **Reminder channel**: {clan_channel}\n'
        f'{emojis.DETAIL} _Reminders will always be sent to this channel._\n'
        f'{emojis.BP} **Reminder role**: {clan_role}\n'
        f'{emojis.DETAIL2} _This role will be pinged by the reminder._\n'
        f'{emojis.DETAIL} _Requires `Manage Server` permission or approval._\n'
    )
    helpers = (
        f'{emojis.BP} **Teamraid guide**: {teamraid_enabled}\n'
        f'{emojis.DETAIL} _Note: If this is on, Molly will track the workers of all guild members using Molly._\n'
    )
    embed = discord.Embed(
        color = settings.EMBED_COLOR,
        title = f'{clan_settings.clan_name.upper()} guild settings',
        description = (
            f'_Settings to set up a guild reminder for the whole guild._\n'
            f'_Molly will ping the set guild role when the reminder is ready._'
        )
    )
    embed.add_field(name='Overview', value=overview, inline=False)
    embed.add_field(name='Reminder', value=reminder, inline=False)
    embed.add_field(name='Helpers', value=helpers, inline=False)
    return embed


async def embed_settings_helpers(bot: discord.Bot, ctx: discord.ApplicationContext, user_settings: users.User) -> discord.Embed:
    """Helper settings embed"""
    raid_guide_mode = 'Compact' if user_settings.helper_raid_compact_mode_enabled else 'Full'
    helpers = (
        f'{emojis.BP} **Affordable upgrades**: {await functions.bool_to_text(user_settings.helper_upgrades_enabled)}\n'
        f'{emojis.DETAIL} _Shows your affordable upgrades when you use '
        f'{await functions.get_game_command(user_settings, "payday")}._\n'
        f'{emojis.BP} **Context commands**: {await functions.bool_to_text(user_settings.helper_context_enabled)}\n'
        f'{emojis.DETAIL} _Shows some helpful commands depending on context._\n'
        f'{emojis.BP} **Profile timers**: {await functions.bool_to_text(user_settings.helper_profile_enabled)}\n'
        f'{emojis.DETAIL} _Shows some useful timers when you open your '
        f'{await functions.get_game_command(user_settings, "profile")}._\n'
        f'{emojis.BP} **Raid guide**: {await functions.bool_to_text(user_settings.helper_raid_enabled)}\n'
        f'{emojis.DETAIL} _Guides you through your raids._\n'
    )
    helper_settings = (
        f'{emojis.BP} **Raid guide mode**: `{raid_guide_mode}`\n'
        f'{emojis.DETAIL} _The compact mode only shows the guide and omits the farm lists._\n'
    )
    embed = discord.Embed(
        color = settings.EMBED_COLOR,
        title = f'{ctx.author.display_name}\'s helper settings',
        description = '_Settings to toggle some helpful little features._'
    )
    embed.add_field(name='Helpers', value=helpers, inline=False)
    embed.add_field(name='Helper settings', value=helper_settings, inline=False)
    return embed


async def embed_settings_messages(bot: discord.Bot, ctx: discord.ApplicationContext,
                                  user_settings: users.User, activity: str) -> List[discord.Embed]:
    """Reminder message specific activity embed"""
    if activity == 'all':
        description = '_If reminders are shown as embeds, the first line is used as the embed title._\n'
        for activity in strings.ACTIVITIES:
            title = f'{ctx.author.display_name}\'s reminder messages'
            activity_column = strings.ACTIVITIES_COLUMNS[activity]
            alert = getattr(user_settings, activity_column)
            alert_message = ''
            for line in alert.message.split('\n'):
                emoji = emojis.DETAIL if line == alert.message.split('\n')[-1] else emojis.DETAIL2
                alert_message = f'{alert_message}\n{emoji} {line}'
            alert_message = (
                f'**{activity.replace("-"," ").capitalize()}**\n'
                f'{alert_message.strip()}\n<:blank:837342790752534528>'
            )
            activity = activity.replace('-',' ').capitalize()
            description = f'{description}\n{alert_message}'
        embed = discord.Embed(
            color = settings.EMBED_COLOR,
            title = title,
            description = description
        )
    else:
        activity_column = strings.ACTIVITIES_COLUMNS[activity]
        alert = getattr(user_settings, activity_column)
        title = f'{activity.replace("-"," ").capitalize()} reminder message'
        embed = discord.Embed(
            color = settings.EMBED_COLOR,
            title = title
        )
        allowed_placeholders = ''
        for placeholder_match in re.finditer('\{(.+?)\}', strings.DEFAULT_MESSAGES_REMINDERS[activity]):
            placeholder = placeholder_match.group(1)
            placeholder_description = strings.PLACEHOLDER_DESCRIPTIONS.get(placeholder, '')
            allowed_placeholders = (
                f'{allowed_placeholders}\n'
                f'{emojis.BP} `{{{placeholder}}}`'
            )
            if placeholder_description != '':
                for line in placeholder_description.split('\n'):
                    emoji = emojis.DETAIL if line == placeholder_description.split('\n')[-1] else emojis.DETAIL2
                    allowed_placeholders = f'{allowed_placeholders}\n{emoji} _{line}_'
        if allowed_placeholders == '':
            allowed_placeholders = '_There are no placeholders available for this message._'
        alert_message = ''
        for line in alert.message.split('\n'):
            emoji = emojis.DETAIL if line == alert.message.split('\n')[-1] else emojis.DETAIL2
            alert_message = f'{alert_message}\n{emoji} {line}'
        embed.add_field(name='Current message', value=alert_message, inline=False)
        embed.add_field(name='Supported placeholders', value=allowed_placeholders.strip(), inline=False)
    return embed


async def embed_settings_reminders(bot: discord.Bot, ctx: discord.ApplicationContext,
                                   user_settings: users.User) -> discord.Embed:
    """Reminder settings embed"""
    message_style = 'Embed' if user_settings.reminders_as_embed else 'Normal message'
    reminder_channel = '`Last channel the reminder was updated in`'
    if user_settings.reminder_channel_id is not None:
        reminder_channel = f'<#{user_settings.reminder_channel_id}>'
    guild_settings: guilds.Guild = await guilds.get_guild(ctx.guild.id)
    prefix = guild_settings.prefix
    behaviour = (
        f'{emojis.BP} **DND mode**: {await functions.bool_to_text(user_settings.dnd_mode_enabled)}\n'
        f'{emojis.DETAIL} _If DND mode is enabled, Molly\'s reminders won\'t ping you._\n'
        f'{emojis.BP} **Slash commands in reminders**: {await functions.bool_to_text(user_settings.reminders_slash_enabled)}\n'
        f'{emojis.DETAIL} _If you can\'t see slash mentions properly, update your Discord app._\n'
        f'{emojis.BP} **Message style**: `{message_style}`\n'
        f'{emojis.BP} **Reminder channel**: {reminder_channel}\n'
        f'{emojis.DETAIL} _If a channel is set, all reminders are sent to that channel._'
    )
    if user_settings.last_claim_time is not None:
        last_claim_time = utils.format_dt(user_settings.last_claim_time, "R")
    else:
        last_claim_time = '`Never`'
    command_reminders = (
        f'{emojis.BP} **Claim**: {await functions.bool_to_text(user_settings.reminder_claim.enabled)}\n'
        f'{emojis.BP} **Daily**: {await functions.bool_to_text(user_settings.reminder_daily.enabled)}\n'
        f'{emojis.BP} **Energy**: {await functions.bool_to_text(user_settings.reminder_energy.enabled)}\n'
        f'{emojis.DETAIL} _You can create a reminder from `{prefix}list` or the profile timers (if enabled)._\n'
        f'{emojis.BP} **Shop items**: {await functions.bool_to_text(user_settings.reminder_shop.enabled)}\n'
        f'{emojis.DETAIL2} _Shows when sold out items are restocked in the {strings.SLASH_COMMANDS["shop list"]}._\n'
        f'{emojis.DETAIL} _Note that you need to open the shop to create reminders._\n'
        f'{emojis.BP} **Vote**: {await functions.bool_to_text(user_settings.reminder_vote.enabled)}\n'
    )
    claim_time = (
        f'{emojis.BP} **Last claim time**: {last_claim_time}\n'
        f'{emojis.DETAIL} _You can manually change this if necessary from the menu below._\n'
    )
    embed = discord.Embed(
        color = settings.EMBED_COLOR,
        title = f'{ctx.author.display_name}\'s reminder settings',
        description = (
            f'_Note that disabling a reminder also deletes the active reminder._'
        )
    )
    embed.add_field(name='Reminder behaviour', value=behaviour, inline=False)
    embed.add_field(name='Reminders', value=command_reminders, inline=False)
    embed.add_field(name='Last claim time', value=claim_time, inline=False)
    return embed


async def embed_settings_server(bot: discord.Bot, ctx: discord.ApplicationContext,
                                guild_settings: guilds.Guild) -> discord.Embed:
    """Server settings embed"""
    server_settings = (
        f'{emojis.BP} **Prefix**: `{guild_settings.prefix}`\n'
    )
    embed = discord.Embed(
        color = settings.EMBED_COLOR,
        title = f'{ctx.guild.name} server settings',
    )
    embed.add_field(name='Settings', value=server_settings, inline=False)
    for event in strings.EVENTS:
        event_settings = getattr(guild_settings, f'event_{event}', None)
        if event_settings is None: continue
        event_enabled = f'{emojis.ENABLED}`Enabled`' if event_settings.enabled else f'{emojis.DISABLED}`Disabled`'
        event_field = (
            f'{emojis.BP} **Event ping**: {event_enabled}\n'
            f'{emojis.BP} **Message**: {event_settings.message}'
        )
        embed.add_field(name=event_settings.name, value=event_field, inline=False)
    return embed


async def embed_settings_user(bot: discord.Bot, ctx: discord.ApplicationContext,
                              user_settings: users.User) -> discord.Embed:
    """User settings embed"""
    bot = (
        f'{emojis.BP} **Bot**: {await functions.bool_to_text(user_settings.bot_enabled)}\n'
        f'{emojis.DETAIL} _You can toggle this with {await functions.get_bot_slash_command(bot, "on")} '
        f'and {await functions.get_bot_slash_command(bot, "off")}._\n'
        f'{emojis.BP} **Reactions**: {await functions.bool_to_text(user_settings.reactions_enabled)}\n'
    )
    tracking = (
        f'{emojis.BP} **Command tracking**: {await functions.bool_to_text(user_settings.tracking_enabled)}\n'
    )
    donor_tier = (
        f'{emojis.BP} **Donor tier**: `{list(strings.DONOR_TIER_ENERGY_MULTIPLIERS)[user_settings.donor_tier].capitalize()}`\n'
    )
    embed = discord.Embed(
        color = settings.EMBED_COLOR,
        title = f'{ctx.author.display_name}\'s user settings',
    )
    embed.add_field(name='Main', value=bot, inline=False)
    embed.add_field(name='Tracking', value=tracking, inline=False)
    embed.add_field(name='Donor tier', value=donor_tier, inline=False)
    return embed