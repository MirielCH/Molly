# components.py
"""Contains global interaction components"""

import asyncio
from datetime import timedelta
import re
from typing import Dict, List, Literal, Optional

import discord
from discord import utils
from humanfriendly import format_timespan

from database import cooldowns, guilds, reminders, users
from resources import emojis, exceptions, functions, modals, settings, strings, views


# --- Miscellaneous ---
class CustomButton(discord.ui.Button):
    """Simple Button. Writes its custom id to the view value, stops the view and does an invisible response."""
    def __init__(self, style: discord.ButtonStyle, custom_id: str, label: Optional[str],
                 emoji: Optional[discord.PartialEmoji] = None):
        super().__init__(style=style, custom_id=custom_id, label=label, emoji=emoji)

    async def callback(self, interaction: discord.Interaction):
        self.view.value = self.custom_id
        self.view.stop()
        try:
            await interaction.response.send_message()
        except Exception:
            pass


# --- Reminder list ---
class DeleteCustomRemindersButton(discord.ui.Button):
    """Button to activate the select to delete custom reminders"""
    def __init__(self, row: Optional[int] = 0):
        super().__init__(style=discord.ButtonStyle.grey, custom_id='activate_select_custom', label='Delete custom reminders',
                         emoji=None, row=row)

    async def callback(self, interaction: discord.Interaction) -> None:
        self.view.remove_item(self)
        self.view.add_item(DeleteCustomReminderSelect(self.view, self.view.custom_reminders, row=2))
        embed = await self.view.embed_function(self.view.bot, self.view.user, self.view.user_settings,
                                               self.view.custom_reminders)
        await interaction.response.edit_message(embed=embed, view=self.view)


class SetClaimReminderTimeButton(discord.ui.Button):
    """Button to activate the select to change the claim reminder time"""
    def __init__(self, row: Optional[int] = 0):
        super().__init__(style=discord.ButtonStyle.grey, custom_id='activate_select_claim', label='Set claim reminder',
                         emoji=None, row=row)

    async def callback(self, interaction: discord.Interaction) -> None:
        self.view.remove_item(self)
        self.view.add_item(SetClaimReminderTimeReminderList(self.view, row=0))
        embed = await self.view.embed_function(self.view.bot, self.view.user, self.view.user_settings,
                                               self.view.custom_reminders)
        await interaction.response.edit_message(embed=embed, view=self.view)


class SetEnergyReminderButton(discord.ui.Button):
    """Button to activate the select to set an energy reminder"""
    def __init__(self, row: Optional[int] = 0):
        super().__init__(style=discord.ButtonStyle.grey, custom_id='activate_select_energy', label='Set energy reminder',
                         emoji=None, row=row)

    async def callback(self, interaction: discord.Interaction) -> None:
        self.view.remove_item(self)
        self.view.add_item(SetEnergyReminder(self.view, row=1))
        embed = await self.view.embed_function(self.view.bot, self.view.user, self.view.user_settings,
                                               self.view.custom_reminders)
        await interaction.response.edit_message(embed=embed, view=self.view)


class DeleteCustomReminderSelect(discord.ui.Select):
    """Select to delete custom reminders"""
    def __init__(self, view: discord.ui.View, custom_reminders: List[reminders.Reminder], row: Optional[int] = None):
        self.custom_reminders = custom_reminders

        options = []
        for reminder in custom_reminders:
            label = f'{reminder.custom_id} - {reminder.message[:92]}'
            options.append(discord.SelectOption(label=label, value=str(reminder.custom_id), emoji=None))
        super().__init__(placeholder='Delete custom reminders', min_values=1, max_values=1, options=options,
                         row=row, custom_id=f'delete_reminders')

    async def callback(self, interaction: discord.Interaction):
        select_value = self.values[0]
        for reminder in self.custom_reminders.copy():
            if reminder.custom_id == int(select_value):
                await reminder.delete()
                self.custom_reminders.remove(reminder)
                for custom_reminder in self.view.custom_reminders:
                    if custom_reminder.custom_id == reminder.custom_id:
                        self.view.user_reminders.remove(custom_reminder)
                        break
        embed = await self.view.embed_function(self.view.bot, self.view.user, self.view.user_settings,
                                               self.view.custom_reminders)
        self.view.remove_item(self)
        if self.custom_reminders:
            self.view.add_item(DeleteCustomReminderSelect(self.view, self.view.custom_reminders, row=2))
        await interaction.response.edit_message(embed=embed, view=self.view)


# --- Settings: General ---
class SwitchSettingsSelect(discord.ui.Select):
    """Select to switch between settings embeds"""
    def __init__(self, view: discord.ui.View, commands_settings: Dict[str, callable], row: Optional[int] = None):
        self.commands_settings = commands_settings
        options = []
        for label in commands_settings.keys():
            options.append(discord.SelectOption(label=label, value=label, emoji=None))
        super().__init__(placeholder='➜ Switch to other settings', min_values=1, max_values=1, options=options, row=row,
                         custom_id='switch_settings')

    async def callback(self, interaction: discord.Interaction):
        select_value = self.values[0]
        await interaction.response.edit_message()
        await self.commands_settings[select_value](self.view.bot, self.view.ctx, switch_view = self.view)


# --- Settings: Clan ---
class ManageClanSettingsSelect(discord.ui.Select):
    """Select to change clan settings"""
    def __init__(self, view: discord.ui.View, row: Optional[int] = None):
        options = []
        reminder_emoji = emojis.ENABLED if view.clan_settings.reminder_enabled else emojis.DISABLED
        alert_contribution_emoji = emojis.ENABLED if view.clan_settings.alert_contribution_enabled else emojis.DISABLED
        options.append(discord.SelectOption(label='Teamraid reminder',
                                            value='toggle_reminder', emoji=reminder_emoji))
        options.append(discord.SelectOption(label='Contribution alert',
                                            value='toggle_alert_contribution', emoji=alert_contribution_emoji))
        options.append(discord.SelectOption(label='Add this channel as guild channel',
                                            value='set_channel', emoji=emojis.ADD))
        options.append(discord.SelectOption(label='Remove guild channel',
                                            value='reset_channel', emoji=emojis.REMOVE))
        options.append(discord.SelectOption(label='Remove guild role',
                                            value='reset_role', emoji=emojis.REMOVE))
        options.append(discord.SelectOption(label='Set reminder offset',
                                            value='set_offset'))
        super().__init__(placeholder='Change reminder settings', min_values=1, max_values=1, options=options, row=row,
                         custom_id='manage_clan_settings')

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.view.clan_settings.leader_id:
            await interaction.response.send_message(
                f'**{interaction.user.display_name}**, you are not registered as the guild owner. Only the guild owner can '
                f'change these settings.\n'
                f'If you _are_ the guild owner, run {strings.SLASH_COMMANDS["guild list"]} to update '
                f'your guild in my database.\n',
                ephemeral=True
            )
            embed = await self.view.embed_function(self.view.bot, self.view.ctx, self.view.clan_settings)
            await interaction.message.edit(embed=embed, view=self.view)
            return
        select_value = self.values[0]
        if select_value == 'toggle_reminder':
            if (not self.view.clan_settings.reminder_enabled
                and (self.view.clan_settings.reminder_channel_id is None or self.view.clan_settings.reminder_role_id is None)):
                await interaction.response.send_message('You need to set a guild channel and a role first.', ephemeral=True)
                embed = await self.view.embed_function(self.view.bot, self.view.ctx, self.view.clan_settings)
                await interaction.message.edit(embed=embed, view=self.view)
                return
            await self.view.clan_settings.update(reminder_enabled=not self.view.clan_settings.reminder_enabled)
        elif select_value == 'toggle_alert_contribution':
            if (not self.view.clan_settings.alert_contribution_enabled
                and (self.view.clan_settings.reminder_channel_id is None or self.view.clan_settings.reminder_role_id is None)):
                await interaction.response.send_message('You need to set a guild channel and a role first.', ephemeral=True)
                embed = await self.view.embed_function(self.view.bot, self.view.ctx, self.view.clan_settings)
                await interaction.message.edit(embed=embed, view=self.view)
                return
            await self.view.clan_settings.update(alert_contribution_enabled=not self.view.clan_settings.alert_contribution_enabled)
        elif select_value == 'set_channel':
            confirm_view = views.ConfirmCancelView(self.view.ctx, styles=[discord.ButtonStyle.blurple, discord.ButtonStyle.grey])
            confirm_interaction = await interaction.response.send_message(
                f'**{interaction.user.display_name}**, do you want to set `{interaction.channel.name}` as the reminder channel '
                f'for the guild `{self.view.clan_settings.clan_name}`?',
                view=confirm_view,
                ephemeral=True
            )
            confirm_view.interaction_message = confirm_interaction
            await confirm_view.wait()
            if confirm_view.value == 'confirm':
                await self.view.clan_settings.update(reminder_channel_id=interaction.channel.id)
                await confirm_interaction.edit_original_response(content='Channel updated.', view=None)
            else:
                await confirm_interaction.edit_original_response(content='Aborted', view=None)
                embed = await self.view.embed_function(self.view.bot, self.view.ctx, self.view.clan_settings)
                await interaction.message.edit(embed=embed, view=self.view)
                return
        elif select_value == 'reset_channel':
            if self.view.clan_settings.reminder_channel_id is None:
                await interaction.response.send_message(
                    f'You don\'t have a reminder channel set already.',
                    ephemeral=True
                )
                embed = await self.view.embed_function(self.view.bot, self.view.ctx, self.view.clan_settings)
                await interaction.message.edit(embed=embed, view=self.view)
                return
            confirm_view = views.ConfirmCancelView(self.view.ctx, styles=[discord.ButtonStyle.red, discord.ButtonStyle.grey])
            confirm_interaction = await interaction.response.send_message(
                f'**{interaction.user.display_name}**, do you want to reset the guild reminder channel '
                f'for the guild `{self.view.clan_settings.clan_name}`?\n\n'
                f'Note that this will also disable the reminder if enabled.',
                view=confirm_view,
                ephemeral=True
            )
            confirm_view.interaction_message = confirm_interaction
            await confirm_view.wait()
            if confirm_view.value == 'confirm':
                await self.view.clan_settings.update(reminder_channel_id=None, reminder_enabled=False)
                await confirm_interaction.edit_original_response(content='Channel reset.', view=None)
            else:
                await confirm_interaction.edit_original_response(content='Aborted', view=None)
                embed = await self.view.embed_function(self.view.bot, self.view.ctx, self.view.clan_settings)
                await interaction.message.edit(embed=embed, view=self.view)
                return
        elif select_value == 'reset_role':
            if self.view.clan_settings.reminder_role_id is None:
                await interaction.response.send_message(
                    f'You don\'t have a role set already.',
                    ephemeral=True
                )
                embed = await self.view.embed_function(self.view.bot, self.view.ctx, self.view.clan_settings)
                await interaction.message.edit(embed=embed, view=self.view)
                return
            confirm_view = views.ConfirmCancelView(self.view.ctx, styles=[discord.ButtonStyle.red, discord.ButtonStyle.grey])
            confirm_interaction = await interaction.response.send_message(
                f'**{interaction.user.display_name}**, do you want to reset the guild reminder role '
                f'for the guild `{self.view.clan_settings.clan_name}`?\n\n'
                f'Note that this will also disable the reminder if enabled.',
                view=confirm_view,
                ephemeral=True
            )
            confirm_view.interaction_message = confirm_interaction
            await confirm_view.wait()
            if confirm_view.value == 'confirm':
                await self.view.clan_settings.update(reminder_role_id=None, reminder_enabled=False)
                await confirm_interaction.edit_original_response(content='Channel reset.', view=None)
            else:
                await confirm_interaction.edit_original_response(content='Aborted', view=None)
                embed = await self.view.embed_function(self.view.bot, self.view.ctx, self.view.clan_settings)
                await interaction.message.edit(embed=embed, view=self.view)
                return
        elif select_value == 'set_offset':
            modal = modals.SetClanReminderOffsetModal(self.view)
            await interaction.response.send_modal(modal)
            return
        for child in self.view.children.copy():
            if isinstance(child, ManageClanSettingsSelect):
                self.view.remove_item(child)
                self.view.add_item(ManageClanSettingsSelect(self.view))
                break
        embed = await self.view.embed_function(self.view.bot, self.view.ctx, self.view.clan_settings)
        if interaction.response.is_done():
            await interaction.message.edit(embed=embed, view=self.view)
        else:
            await interaction.response.edit_message(embed=embed, view=self.view)


class SetClanReminderRoleSelect(discord.ui.Select):
    """Select to change the clan reminder role"""
    def __init__(self, view: discord.ui.View, disabled: Optional[bool] = False, row: Optional[int] = None):
        super().__init__(select_type=discord.ComponentType.role_select, placeholder='Select guild role', min_values=1, max_values=1, row=row,
                         custom_id='set_clan_role', disabled=disabled)

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.view.clan_settings.leader_id:
            await interaction.response.send_message(
                f'**{interaction.user.display_name}**, you are not registered as the guild owner. Only the guild owner can '
                f'change these settings.\n'
                f'If you _are_ the guild owner, run {strings.SLASH_COMMANDS["guild list"]} to update '
                f'your guild in my database.\n',
                ephemeral=True
            )
            embed = await self.view.embed_function(self.view.bot, self.view.ctx, self.view.clan_settings)
            await interaction.message.edit(embed=embed, view=self.view)
            return
        new_role = self.values[0]
        if not interaction.user.guild_permissions.manage_guild:
            approval_view = views.ApprovalView(self.view.ctx, discord.ButtonStyle.green, label='Approve', custom_id='approve', emoji=emojis.ENABLED)
            approval_interaction = await interaction.response.send_message(
                f'**Approval required**\n\n'
                f'**{interaction.user.display_name}**, changing the guild reminder role for the '
                f'guild `{self.view.clan_settings.clan_name.upper()}` to {new_role.mention} (ID `{new_role.id}`) '
                f'requires approval.\n\n'
                f'Please have someone with `Manage Server` permission click the button below to confirm this change.',
                view=approval_view
            )
            approval_view.interaction_message = approval_interaction
            await approval_view.wait()
            if approval_view.value == 'abort':
                await approval_interaction.edit_original_response(content = 'Aborted.', view=None)
            elif approval_view.value == 'approve':
                await self.view.clan_settings.update(reminder_role_id=new_role.id)
                await approval_interaction.edit_original_response(
                    content = (
                        f'**Change approved**\n\n'
                        f'The reminder role for the guild `{self.view.clan_settings.clan_name.upper()}` was changed to '
                        f'`{new_role.name}` (ID `{new_role.id}`)'
                    ),
                    view=None
                )
        else:
            await self.view.clan_settings.update(reminder_role_id=new_role.id)
        for child in self.view.children.copy():
            if isinstance(child, SetClanReminderRoleSelect):
                self.view.remove_item(child)
                self.view.add_item(SetClanReminderRoleSelect(self.view))
                break
        embed = await self.view.embed_function(self.view.bot, self.view.ctx, self.view.clan_settings)
        if interaction.response.is_done():
            await interaction.message.edit(embed=embed, view=self.view)
        else:
            await interaction.response.edit_message(embed=embed, view=self.view)


# --- Settings: Helpers ---
class ManageHelperSettingsSelect(discord.ui.Select):
    """Select to change helper settings"""
    def __init__(self, view: discord.ui.View, row: Optional[int] = None):
        options = []
        raid_helper_mode = 'compact mode' if not view.user_settings.helper_raid_compact_mode_enabled else 'full mode'
        worker_names_emoji = emojis.ENABLED if view.user_settings.helper_raid_names_enabled else emojis.DISABLED
        ready_commands_emoji = emojis.ENABLED if view.user_settings.helper_profile_ready_commands_visible else emojis.DISABLED
        options.append(discord.SelectOption(label=f'Raid guide: Switch to {raid_helper_mode}',
                                            value='toggle_raid_guide_mode'))
        options.append(discord.SelectOption(label=f'Raid guide: Worker names', emoji=worker_names_emoji,
                                            value='toggle_raid_names'))
        options.append(discord.SelectOption(label=f'Profile timers: Ready commands', emoji=ready_commands_emoji,
                                            value='toggle_ready_commands'))
        super().__init__(placeholder='Change helper settings', min_values=1, max_values=1, options=options, row=row,
                         custom_id='manage_helper_settings')

    async def callback(self, interaction: discord.Interaction):
        select_value = self.values[0]
        if select_value == 'toggle_raid_guide_mode':
            await self.view.user_settings.update(
                helper_raid_compact_mode_enabled=not self.view.user_settings.helper_raid_compact_mode_enabled
            )
        elif select_value == 'toggle_raid_names':
            await self.view.user_settings.update(
                helper_raid_names_enabled=not self.view.user_settings.helper_raid_names_enabled
            )
        elif select_value == 'toggle_ready_commands':
            await self.view.user_settings.update(
                helper_profile_ready_commands_visible=not self.view.user_settings.helper_profile_ready_commands_visible
            )
        for child in self.view.children.copy():
            if isinstance(child, ManageHelperSettingsSelect):
                self.view.remove_item(child)
                self.view.add_item(ManageHelperSettingsSelect(self.view))
                break
        embed = await self.view.embed_function(self.view.bot, self.view.ctx, self.view.user_settings)
        if interaction.response.is_done():
            await interaction.message.edit(embed=embed, view=self.view)
        else:
            await interaction.response.edit_message(embed=embed, view=self.view)

# --- Settings: Reminders ---
class ManageReminderSettingsSelect(discord.ui.Select):
    """Select to change reminder settings settings"""
    def __init__(self, view: discord.ui.View, row: Optional[int] = None):
        options = []
        dnd_emoji = emojis.ENABLED if view.user_settings.dnd_mode_enabled else emojis.DISABLED
        slash_emoji = emojis.ENABLED if view.user_settings.reminders_slash_enabled else emojis.DISABLED
        message_style = 'a normal message' if view.user_settings.reminders_as_embed else 'an embed'
        options.append(discord.SelectOption(label=f'DND mode', emoji=dnd_emoji,
                                            value='toggle_dnd'))
        options.append(discord.SelectOption(label=f'Slash commands in reminders', emoji=slash_emoji,
                                            value='toggle_slash'))
        options.append(discord.SelectOption(label=f'Show reminders in {message_style}', emoji=None,
                                            value='toggle_message_style'))
        options.append(discord.SelectOption(label='Add this channel as reminder channel', emoji=emojis.ADD,
                                            value='set_channel'))
        if view.user_settings.reminder_channel_id is not None:
            options.append(discord.SelectOption(label='Remove reminder channel', emoji=emojis.REMOVE,
                                                value='reset_channel'))
        options.append(discord.SelectOption(label=f'Change daily reminder offset',
                                            value='set_daily_offset', emoji=None))
        options.append(discord.SelectOption(label=f'Change last claim time',
                                            value='set_last_claim', emoji=None))
        super().__init__(placeholder='Change settings', min_values=1, max_values=1, options=options, row=row,
                         custom_id='manage_user_settings')

    async def callback(self, interaction: discord.Interaction):
        select_value = self.values[0]
        if select_value == 'toggle_dnd':
            await self.view.user_settings.update(dnd_mode_enabled=not self.view.user_settings.dnd_mode_enabled)
        elif select_value == 'toggle_slash':
            await self.view.user_settings.update(reminders_slash_enabled=not self.view.user_settings.reminders_slash_enabled)
        elif select_value == 'toggle_message_style':
            await self.view.user_settings.update(reminders_as_embed=not self.view.user_settings.reminders_as_embed)
        elif select_value == 'set_channel':
            confirm_view = views.ConfirmCancelView(self.view.ctx, styles=[discord.ButtonStyle.blurple, discord.ButtonStyle.grey])
            confirm_interaction = await interaction.response.send_message(
                f'**{interaction.user.display_name}**, do you want to set `{interaction.channel.name}` as the reminder '
                f'channel?\n'
                f'If a reminder channel is set, all reminders will be sent to that channel.\n',
                view=confirm_view,
                ephemeral=True
            )
            confirm_view.interaction_message = confirm_interaction
            await confirm_view.wait()
            if confirm_view.value == 'confirm':
                await self.view.user_settings.update(reminder_channel_id=interaction.channel.id)
                await confirm_interaction.edit_original_response(content='Channel updated.', view=None)
            else:
                await confirm_interaction.edit_original_response(content='Aborted', view=None)
        elif select_value == 'reset_channel':
            confirm_view = views.ConfirmCancelView(self.view.ctx, styles=[discord.ButtonStyle.red, discord.ButtonStyle.grey])
            confirm_interaction = await interaction.response.send_message(
                f'**{interaction.user.display_name}**, do you want to reset your reminder channel?\n\n'
                f'If you do this, reminders will be sent to where you create them.',
                view=confirm_view,
                ephemeral=True
            )
            confirm_view.interaction_message = confirm_interaction
            await confirm_view.wait()
            if confirm_view.value == 'confirm':
                await self.view.user_settings.update(reminder_channel_id=None)
                await confirm_interaction.edit_original_response(content='Channel reset.', view=None)
            else:
                await confirm_interaction.edit_original_response(content='Aborted', view=None)
        elif select_value == 'set_daily_offset':
            modal = modals.SetDailyReminderOffsetModal(self.view)
            await interaction.response.send_modal(modal)
            return
        elif select_value == 'set_last_claim':
            modal = modals.SetLastClaimModal(self.view)
            await interaction.response.send_modal(modal)
            return
        for child in self.view.children.copy():
            if isinstance(child, ManageReminderSettingsSelect):
                self.view.remove_item(child)
                self.view.add_item(ManageReminderSettingsSelect(self.view))
                break
        embed = await self.view.embed_function(self.view.bot, self.view.ctx, self.view.user_settings)
        if interaction.response.is_done():
            await interaction.message.edit(embed=embed, view=self.view)
        else:
            await interaction.response.edit_message(embed=embed, view=self.view)


# --- Settings: Reminder messages ---
class ReminderMessageSelect(discord.ui.Select):
    """Select to select reminder messages by activity"""
    def __init__(self, view: discord.ui.View, activities: List[str], placeholder: str, custom_id: str,
                 row: Optional[int] = None):
        options = []
        options.append(discord.SelectOption(label='All', value='all', emoji=None))
        for activity in activities:
            options.append(discord.SelectOption(label=activity.replace('-',' ').capitalize(), value=activity, emoji=None))
        super().__init__(placeholder=placeholder, min_values=1, max_values=1, options=options, row=row,
                         custom_id=custom_id)

    async def callback(self, interaction: discord.Interaction):
        select_value = self.values[0]
        self.view.activity = select_value
        all_custom_ids = []
        for child in self.view.children:
            all_custom_ids.append(child.custom_id)
        if select_value == 'all':
            if 'set_message' in all_custom_ids or 'reset_message' in all_custom_ids:
                for child in self.view.children.copy():
                    if child.custom_id in ('set_message', 'reset_message'):
                        self.view.remove_item(child)
            if 'reset_all' not in all_custom_ids:
                self.view.add_item(SetReminderMessageButton(style=discord.ButtonStyle.red, custom_id='reset_all',
                                                            label='Reset all messages', row=1))
        else:
            if 'reset_all' in all_custom_ids:
                for child in self.view.children.copy():
                    if child.custom_id == 'reset_all':
                        self.view.remove_item(child)
            if 'set_message' not in all_custom_ids:
                self.view.add_item(SetReminderMessageButton(style=discord.ButtonStyle.blurple, custom_id='set_message',
                                                            label='Change', row=1))
            if 'reset_message' not in all_custom_ids:
                self.view.add_item(SetReminderMessageButton(style=discord.ButtonStyle.red, custom_id='reset_message',
                                                            label='Reset', row=1))
        embed = await self.view.embed_function(self.view.bot, self.view.ctx, self.view.user_settings, select_value)
        await interaction.response.edit_message(embed=embed, view=self.view)


class SetReminderMessageButton(discord.ui.Button):
    """Button to edit reminder messages"""
    def __init__(self, style: discord.ButtonStyle, custom_id: str, label: str, disabled: Optional[bool] = False,
                 emoji: Optional[discord.PartialEmoji] = None, row: Optional[int] = 1):
        super().__init__(style=style, custom_id=custom_id, label=label, emoji=emoji,
                         disabled=disabled, row=row)

    async def callback(self, interaction: discord.Interaction) -> None:
        def check(m: discord.Message) -> bool:
            return m.author == interaction.user and m.channel == interaction.channel

        if self.custom_id == 'reset_all':
            confirm_view = views.ConfirmCancelView(self.view.ctx, styles=[discord.ButtonStyle.red, discord.ButtonStyle.grey])
            confirm_interaction = await interaction.response.send_message(
                f'**{interaction.user.display_name}**, this will reset **all** messages to the default one. '
                f'Are you sure?',
                view=confirm_view,
                ephemeral=True
            )
            confirm_view.interaction_message = confirm_interaction
            await confirm_view.wait()
            if confirm_view.value == 'confirm':
                kwargs = {}
                for activity in strings.ACTIVITIES:
                    activity_column = strings.ACTIVITIES_COLUMNS[activity]
                    kwargs[f'{activity_column}_message'] = strings.DEFAULT_MESSAGES_REMINDERS[activity]
                await self.view.user_settings.update(**kwargs)
                await interaction.edit_original_response(
                    content=(
                        f'Changed all messages back to their default message.\n\n'
                        f'Note that running reminders do not update automatically.'
                    ),
                    view=None
                )
                embed = await self.view.embed_function(self.view.bot, self.view.ctx, self.view.user_settings,
                                                        self.view.activity)
                await interaction.message.edit(embed=embed, view=self.view)
                return
            else:
                await confirm_interaction.edit_original_response(content='Aborted', view=None)
                return
        elif self.custom_id == 'set_message':
            await interaction.response.send_message(
                f'**{interaction.user.display_name}**, please send the new reminder message to this channel (or `abort` to abort):',
            )
            try:
                answer = await self.view.bot.wait_for('message', check=check, timeout=60)
            except asyncio.TimeoutError:
                await interaction.edit_original_response(content=f'**{interaction.user.display_name}**, you didn\'t answer in time.')
                return
            if answer.mentions:
                for user in answer.mentions:
                    if user != answer.author:
                        await interaction.delete_original_response(delay=5)
                        followup_message = await interaction.followup.send(
                            content='Aborted. Please don\'t ping other people in your reminders.',
                        )
                        await followup_message.delete(delay=5)
                        return
            new_message = answer.content
            role_match = re.search(r'<@&(\d+)>', answer.content.lower())
            if role_match or '@here' in answer.content.lower() or '@everyone' in answer.content.lower():
                await interaction.delete_original_response(delay=5)
                followup_message = await interaction.followup.send(
                    content='Aborted. Pinging roles, everyone or here is not allowed in reminders.',
                )
                await followup_message.delete(delay=5)
                return
            if new_message.lower() in ('abort','cancel','stop'):
                await interaction.delete_original_response(delay=3)
                followup_message = await interaction.followup.send('Aborted.')
                await followup_message.delete(delay=3)
                return
            if len(new_message) > 200:
                await interaction.delete_original_response(delay=5)
                followup_message = await interaction.followup.send(
                    'This is a command to set a new message, not to write a novel :thinking:',
                )
                await followup_message.delete(delay=5)
                return
            for placeholder in re.finditer('\{(.+?)\}', new_message):
                placeholder_str = placeholder.group(1)
                if placeholder_str not in strings.DEFAULT_MESSAGES_REMINDERS[self.view.activity]:
                    allowed_placeholders = ''
                    for placeholder in re.finditer('\{(.+?)\}', strings.DEFAULT_MESSAGES_REMINDERS[self.view.activity]):
                        allowed_placeholders = (
                            f'{allowed_placeholders}\n'
                            f'{emojis.BP} {{{placeholder.group(1)}}}'
                        )
                    if allowed_placeholders == '':
                        allowed_placeholders = f'There are no placeholders available for this message.'
                    else:
                        allowed_placeholders = (
                            f'Available placeholders for this message:\n'
                            f'{allowed_placeholders.strip()}'
                        )
                    await interaction.delete_original_response(delay=3)
                    followup_message = await interaction.followup.send(
                        f'Invalid placeholder found.\n\n'
                        f'{allowed_placeholders}',
                        ephemeral=True
                    )
                    await followup_message.delete(delay=3)
                    return
            await interaction.delete_original_response(delay=3)
            followup_message = await interaction.followup.send(
                f'Message updated!\n\n'
                f'Note that running reminders do not update automatically.'
            )
            await followup_message.delete(delay=3)
        elif self.custom_id == 'reset_message':
            new_message = strings.DEFAULT_MESSAGES_REMINDERS[self.view.activity]
        kwargs = {}
        activity_column = strings.ACTIVITIES_COLUMNS[self.view.activity]
        kwargs[f'{activity_column}_message'] = new_message
        await self.view.user_settings.update(**kwargs)
        embed = await self.view.embed_function(self.view.bot, self.view.ctx, self.view.user_settings, self.view.activity)
        if interaction.response.is_done():
            await interaction.message.edit(embed=embed, view=self.view)
        else:
            await interaction.response.edit_message(embed=embed, view=self.view)


# --- Settings: Server ---
class ManageServerSettingsSelect(discord.ui.Select):
    """Select to change server settings"""
    def __init__(self, view: discord.ui.View, row: Optional[int] = None):
        options = []
        options.append(discord.SelectOption(label='Change prefix',
                                            value='set_prefix', emoji=None))
        super().__init__(placeholder='Change settings', min_values=1, max_values=1, options=options, row=row,
                         custom_id='manage_server_settings')

    async def callback(self, interaction: discord.Interaction):
        select_value = self.values[0]
        if select_value == 'set_prefix':
            modal = modals.SetPrefixModal(self.view)
            await interaction.response.send_modal(modal)
            return
        for child in self.view.children.copy():
            if isinstance(child, ManageServerSettingsSelect):
                self.view.remove_item(child)
                self.view.add_item(ManageServerSettingsSelect(self.view))
                break
        embed = await self.view.embed_function(self.view.bot, self.view.ctx, self.view.guild_settings)
        if interaction.response.is_done():
            await interaction.message.edit(embed=embed, view=self.view)
        else:
            await interaction.response.edit_message(embed=embed, view=self.view)


class ManageEventPingMessagesSelect(discord.ui.Select):
    """Select to change event ping messages"""
    def __init__(self, view: discord.ui.View, row: Optional[int] = None):
        options = []
        for event in strings.EVENTS:
            event_settings = getattr(view.guild_settings, f'event_{event}', None)
            if event_settings is None: continue
            options.append(discord.SelectOption(label=f'Change {event_settings.name} message',
                                                value=f'set_{event}_message'))
        options.append(discord.SelectOption(label='Reset all messages',
                                            value='reset_messages'))
        super().__init__(placeholder='Change messages', min_values=1, max_values=1, options=options, row=row,
                         custom_id='manage_event_messages')

    async def callback(self, interaction: discord.Interaction):
        def check(m: discord.Message) -> bool:
            return m.author == interaction.user and m.channel == interaction.channel

        select_value = self.values[0]
        if select_value == 'reset_messages':
            confirm_view = views.ConfirmCancelView(self.view.ctx, styles=[discord.ButtonStyle.red, discord.ButtonStyle.grey])
            confirm_interaction = await interaction.response.send_message(
                f'**{interaction.user.display_name}**, this will reset **all** event ping messages to the default one. '
                f'Are you sure?',
                view=confirm_view,
                ephemeral=True
            )
            confirm_view.interaction_message = confirm_interaction
            await confirm_view.wait()
            if confirm_view.value == 'confirm':
                kwargs = {}
                for event in strings.EVENTS:
                    activity_column = f'event_{event}_message'
                    kwargs[activity_column] = strings.DEFAULT_MESSAGES_EVENTS[event]
                await self.view.guild_settings.update(**kwargs)
                await interaction.edit_original_response(
                    content=(
                        f'Changed all event messages back to their default message.'
                    ),
                    view=None,
                )
                embed = await self.view.embed_function(self.view.bot, self.view.ctx, self.view.guild_settings)
                await interaction.message.edit(embed=embed, view=self.view)
                return
            else:
                await confirm_interaction.edit_original_response(content='Aborted', view=None)
                return
        else:
            event = re.search(r'set_(\w+)_message', select_value).group(1)
            event_settings = getattr(self.view.guild_settings, f'event_{event}', None)
            if event_settings is None:
                await interaction.response.send_message(strings.MSG_ERROR)
                embed = await self.view.embed_function(self.view.bot, self.view.ctx, self.view.guild_settings)
                await interaction.message.edit(embed=embed, view=self.view)
                return
            await interaction.response.send_message(
                f'**{interaction.user.display_name}**, please send the new message for the {event_settings.name} event to this '
                f'channel (or `abort` to abort):',
            )
            try:
                answer = await self.view.bot.wait_for('message', check=check, timeout=60)
            except asyncio.TimeoutError:
                await interaction.edit_original_response(content=f'**{interaction.user.display_name}**, you didn\'t answer in time.')
                return
            new_message = answer.content
            if new_message.lower() in ('abort','cancel','stop'):
                await interaction.delete_original_response(delay=3)
                followup_message = await interaction.followup.send('Aborted.')
                await followup_message.delete(delay=3)
                embed = await self.view.embed_function(self.view.bot, self.view.ctx, self.view.guild_settings)
                await interaction.message.edit(embed=embed, view=self.view)
                return
            if len(new_message) > 800:
                await interaction.delete_original_response(delay=5)
                followup_message = await interaction.followup.send(
                    'This is a command to set a new message, not to write a novel :thinking:',
                )
                await followup_message.delete(delay=5)
                embed = await self.view.embed_function(self.view.bot, self.view.ctx, self.view.guild_settings)
                await interaction.message.edit(embed=embed, view=self.view)
                return
            await interaction.delete_original_response(delay=3)
            kwargs = {f'event_{event}_message': new_message}
            await self.view.guild_settings.update(**kwargs)
            followup_message = await interaction.followup.send('Message updated!')
            await followup_message.delete(delay=3)
        for child in self.view.children.copy():
            if isinstance(child, ManageServerSettingsSelect):
                self.view.remove_item(child)
                self.view.add_item(ManageServerSettingsSelect(self.view))
                break
        embed = await self.view.embed_function(self.view.bot, self.view.ctx, self.view.guild_settings)
        if interaction.response.is_done():
            await interaction.message.edit(embed=embed, view=self.view)
        else:
            await interaction.response.edit_message(embed=embed, view=self.view)


# --- Settings: User ---
class ManageUserSettingsSelect(discord.ui.Select):
    """Select to change user settings"""
    def __init__(self, view: discord.ui.View, row: Optional[int] = None):
        options = []
        reactions_emoji = emojis.ENABLED if view.user_settings.reactions_enabled else emojis.DISABLED
        dnd_emoji = emojis.ENABLED if view.user_settings.dnd_mode_enabled else emojis.DISABLED
        slash_emoji = emojis.ENABLED if view.user_settings.reminders_slash_enabled else emojis.DISABLED
        tracking_emoji = emojis.ENABLED if view.user_settings.tracking_enabled else emojis.DISABLED
        options.append(discord.SelectOption(label=f'Reactions', emoji=reactions_emoji,
                                            value='toggle_reactions'))
        options.append(discord.SelectOption(label=f'Command tracking', emoji=tracking_emoji,
                                            value='toggle_tracking'))
        super().__init__(placeholder='Change settings', min_values=1, max_values=1, options=options, row=row,
                         custom_id='manage_user_settings')

    async def callback(self, interaction: discord.Interaction):
        select_value = self.values[0]
        if select_value == 'toggle_reactions':
            await self.view.user_settings.update(reactions_enabled=not self.view.user_settings.reactions_enabled)
        elif select_value == 'toggle_tracking':
            await self.view.user_settings.update(tracking_enabled=not self.view.user_settings.tracking_enabled)
        for child in self.view.children.copy():
            if isinstance(child, ManageUserSettingsSelect):
                self.view.remove_item(child)
                self.view.add_item(ManageUserSettingsSelect(self.view))
                break
        embed = await self.view.embed_function(self.view.bot, self.view.ctx, self.view.user_settings)
        if interaction.response.is_done():
            await interaction.message.edit(embed=embed, view=self.view)
        else:
            await interaction.response.edit_message(embed=embed, view=self.view)


class ToggleServerSettingsSelect(discord.ui.Select):
    """Toggle select that shows and toggles the status of server settings."""
    def __init__(self, view: discord.ui.View, toggled_settings: Dict[str, str], placeholder: str,
                 custom_id: Optional[str] = 'toggle_server_settings', row: Optional[int] = None):
        self.toggled_settings = toggled_settings
        options = []
        if len(toggled_settings) > 1:
            options.append(discord.SelectOption(label='Enable all', value='enable_all', emoji=None))
            options.append(discord.SelectOption(label='Disable all', value='disable_all', emoji=None))
        for label, setting in toggled_settings.items():
            setting_enabled = getattr(view.guild_settings, setting)
            if isinstance(setting_enabled, guilds.EventPing):
                setting_enabled = getattr(setting_enabled, 'enabled')
            emoji = emojis.ENABLED if setting_enabled else emojis.DISABLED
            options.append(discord.SelectOption(label=label, value=setting, emoji=emoji))
        super().__init__(placeholder=placeholder, min_values=1, max_values=1, options=options, row=row,
                         custom_id=custom_id)

    async def callback(self, interaction: discord.Interaction):
        select_value = self.values[0]
        kwargs = {}
        if select_value in ('enable_all','disable_all'):
            enabled = True if select_value == 'enable_all' else False
            for setting in self.toggled_settings.values():
                if not setting.endswith('_enabled'):
                    setting = f'{setting}_enabled'
                kwargs[setting] = enabled
        else:
            setting_value = getattr(self.view.guild_settings, select_value)
            if isinstance(setting_value, guilds.EventPing):
                setting_value = getattr(setting_value, 'enabled')
            if not select_value.endswith('_enabled'):
                select_value = f'{select_value}_enabled'
            kwargs[select_value] = not setting_value
        await self.view.guild_settings.update(**kwargs)
        for child in self.view.children.copy():
            if child.custom_id == self.custom_id:
                self.view.remove_item(child)
                self.view.add_item(ToggleServerSettingsSelect(self.view, self.toggled_settings,
                                                            self.placeholder, self.custom_id))
                break
        embed = await self.view.embed_function(self.view.bot, self.view.ctx, self.view.guild_settings)
        await interaction.response.edit_message(embed=embed, view=self.view)


class ToggleClanSettingsSelect(discord.ui.Select):
    """Toggle select that shows and toggles the status of clan settings."""
    def __init__(self, view: discord.ui.View, toggled_settings: Dict[str, str], placeholder: str,
                 custom_id: Optional[str] = 'toggle_clan_settings', row: Optional[int] = None):
        self.toggled_settings = toggled_settings
        options = []
        if len(toggled_settings) > 1:
            options.append(discord.SelectOption(label='Enable all', value='enable_all', emoji=None))
            options.append(discord.SelectOption(label='Disable all', value='disable_all', emoji=None))
        for label, setting in toggled_settings.items():
            setting_enabled = getattr(view.clan_settings, setting)
            emoji = emojis.ENABLED if setting_enabled else emojis.DISABLED
            options.append(discord.SelectOption(label=label, value=setting, emoji=emoji))
        super().__init__(placeholder=placeholder, min_values=1, max_values=1, options=options, row=row,
                         custom_id=custom_id)

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.view.clan_settings.leader_id:
            await interaction.response.send_message(
                f'**{interaction.user.display_name}**, you are not registered as the guild owner. Only the guild owner can '
                f'change these settings.\n'
                f'If you _are_ the guild owner, run {strings.SLASH_COMMANDS["guild list"]} to update '
                f'your guild in my database.\n',
                ephemeral=True
            )
            embed = await self.view.embed_function(self.view.bot, self.view.ctx, self.view.clan_settings)
            await interaction.message.edit(embed=embed, view=self.view)
            return
        select_value = self.values[0]
        kwargs = {}
        if select_value in ('enable_all','disable_all'):
            enabled = True if select_value == 'enable_all' else False
            for setting in self.toggled_settings.values():
                if not setting.endswith('_enabled'):
                    setting = f'{setting}_enabled'
                kwargs[setting] = enabled
        else:
            setting_value = getattr(self.view.clan_settings, select_value)
            new_setting_value = not setting_value
            if not select_value.endswith('_enabled'):
                select_value = f'{select_value}_enabled'
            kwargs[select_value] = new_setting_value
        await self.view.clan_settings.update(**kwargs)
        for child in self.view.children.copy():
            if child.custom_id == self.custom_id:
                self.view.remove_item(child)
                self.view.add_item(ToggleClanSettingsSelect(self.view, self.toggled_settings,
                                                            self.placeholder, self.custom_id))
                break
        embed = await self.view.embed_function(self.view.bot, self.view.ctx, self.view.clan_settings)
        await interaction.response.edit_message(embed=embed, view=self.view)
        if new_setting_value and select_value == 'helper_teamraid_enabled':
            await interaction.followup.send(
                f'To use the teamraid guide, please use '
                f'{await functions.get_game_command(self.view.user_settings, "worker stats")} to update your workers.',
                ephemeral=True
            )


class ToggleUserSettingsSelect(discord.ui.Select):
    """Toggle select that shows and toggles the status of user settings (except alerts)."""
    def __init__(self, view: discord.ui.View, toggled_settings: Dict[str, str], placeholder: str,
                 custom_id: Optional[str] = 'toggle_user_settings', row: Optional[int] = None):
        self.toggled_settings = toggled_settings
        options = []
        if len(toggled_settings) > 1:
            options.append(discord.SelectOption(label='Enable all', value='enable_all', emoji=None))
            options.append(discord.SelectOption(label='Disable all', value='disable_all', emoji=None))
        for label, setting in toggled_settings.items():
            setting_enabled = getattr(view.user_settings, setting)
            if isinstance(setting_enabled, users.UserReminder):
                setting_enabled = getattr(setting_enabled, 'enabled')
            emoji = emojis.ENABLED if setting_enabled else emojis.DISABLED
            options.append(discord.SelectOption(label=label, value=setting, emoji=emoji))
        super().__init__(placeholder=placeholder, min_values=1, max_values=1, options=options, row=row,
                         custom_id=custom_id)

    async def callback(self, interaction: discord.Interaction):
        select_value = self.values[0]
        kwargs = {}
        if select_value in ('enable_all','disable_all'):
            new_setting_value = True if select_value == 'enable_all' else False
            reminder_settings = False
            for setting in self.toggled_settings.values():
                if not setting.endswith('_enabled'):
                    setting = f'{setting}_enabled'
                kwargs[setting] = new_setting_value
                if setting.startswith('reminder_'):
                    reminder_settings = True
            if not new_setting_value and reminder_settings:
                try:
                    user_reminders = await reminders.get_active_user_reminders(self.view.user.id)
                    for reminder in user_reminders:
                        await reminder.delete()
                except exceptions.NoDataFoundError:
                    pass
        else:
            setting_value = getattr(self.view.user_settings, select_value)
            if isinstance(setting_value, users.UserReminder):
                setting_value = getattr(setting_value, 'enabled')
                if setting_value:
                    try:
                        reminder: reminders.Reminder = await reminders.get_user_reminder(self.view.user.id,
                                                                                         select_value.replace('reminder_',''))
                        await reminder.delete()
                    except exceptions.NoDataFoundError:
                        pass
            new_setting_value = not setting_value
            if not select_value.endswith('_enabled'):
                select_value = f'{select_value}_enabled'
            kwargs[select_value] = new_setting_value
        await self.view.user_settings.update(**kwargs)
        for child in self.view.children.copy():
            if child.custom_id == self.custom_id:
                self.view.remove_item(child)
                self.view.add_item(ToggleUserSettingsSelect(self.view, self.toggled_settings,
                                                            self.placeholder, self.custom_id))
                break
        embed = await self.view.embed_function(self.view.bot, self.view.ctx, self.view.user_settings)
        await interaction.response.edit_message(embed=embed, view=self.view)
        if new_setting_value and 'helper_raid_enabled' in kwargs:
            await interaction.followup.send(
                f'To use the raid guide, please use '
                f'{await functions.get_game_command(self.view.user_settings, "worker stats")} to update your workers.',
                ephemeral=True
            )


# --- Tracking ---
class ToggleTrackingButton(discord.ui.Button):
    """Button to toggle the auto-ready feature"""
    def __init__(self, style: Optional[discord.ButtonStyle], custom_id: str, label: str,
                 disabled: bool = False, emoji: Optional[discord.PartialEmoji] = None):
        super().__init__(style=style, custom_id=custom_id, label=label, emoji=emoji,
                         disabled=disabled, row=1)

    async def callback(self, interaction: discord.Interaction) -> None:
        enabled = True if self.custom_id == 'track' else False
        await self.view.user_settings.update(tracking_enabled=enabled)
        self.view.value = self.custom_id
        await self.view.user_settings.refresh()
        if self.view.user_settings.tracking_enabled:
            self.style = discord.ButtonStyle.grey
            self.label = 'Stop tracking me!'
            self.custom_id = 'untrack'
        else:
            self.style = discord.ButtonStyle.green
            self.label = 'Track me!'
            self.custom_id = 'track'
        if not interaction.response.is_done():
            await interaction.response.edit_message(view=self.view)
        else:
            await self.view.message.edit(view=self.view)


# --- Dev ---
class CopyEventReductionsButton(discord.ui.Button):
    """Button to toggle the auto-ready feature"""
    def __init__(self, style: Optional[discord.ButtonStyle], custom_id: str, label: str,
                 disabled: bool = False, emoji: Optional[discord.PartialEmoji] = None):
        super().__init__(style=style, custom_id=custom_id, label=label, emoji=emoji,
                         disabled=disabled)

    async def callback(self, interaction: discord.Interaction) -> None:
        for cooldown in self.view.all_cooldowns:
            if self.custom_id == 'copy_slash_text':
                await cooldown.update(event_reduction_mention=cooldown.event_reduction_slash)
            else:
                await cooldown.update(event_reduction_slash=cooldown.event_reduction_mention)
        embed = await self.view.embed_function(self.view.all_cooldowns)
        if not interaction.response.is_done():
            await interaction.response.edit_message(embed=embed, view=self.view)
        else:
            await self.view.message.edit(embed=embed, view=self.view)


class ManageEventReductionsSelect(discord.ui.Select):
    """Select to manage cooldowns"""
    def __init__(self, view: discord.ui.View, all_cooldowns: List[cooldowns.Cooldown],
                 cd_type: Literal['slash', 'text'], row: Optional[int] = None):
        self.all_cooldowns = all_cooldowns
        self.cd_type = cd_type
        options = []
        options.append(discord.SelectOption(label=f'All',
                                            value='all'))
        for cooldown in all_cooldowns:
            options.append(discord.SelectOption(label=cooldown.activity.capitalize(),
                                                value=cooldown.activity))
            cooldown.update()
        placeholders = {
            'slash': 'Change slash event reductions',
            'text': 'Change text event reductions',
        }
        super().__init__(placeholder=placeholders[cd_type], min_values=1, max_values=1, options=options, row=row,
                         custom_id=f'manage_{cd_type}')

    async def callback(self, interaction: discord.Interaction):
        select_value = self.values[0]
        modal = modals.SetEventReductionModal(self.view, select_value, self.cd_type)
        await interaction.response.send_modal(modal)


class SetClaimReminderTime(discord.ui.Select):
    """Select to set the time of a claim reminder"""
    def __init__(self, view: discord.ui.View, disabled: Optional[bool] = False, row: Optional[int] = None):
        options = [
            discord.SelectOption(label='1h of production time', value='1'),
            discord.SelectOption(label='2h of production time', value='2'),
            discord.SelectOption(label='4h of production time', value='4'),
            discord.SelectOption(label='6h of production time', value='6'),
            discord.SelectOption(label='8h of production time', value='8'),
            discord.SelectOption(label='10h of production time', value='10'),
            discord.SelectOption(label='12h of production time', value='12'),
            discord.SelectOption(label='16h of production time', value='16'),
            discord.SelectOption(label='20h of production time', value='20'),
            discord.SelectOption(label='24h of production time', value='24'),
            discord.SelectOption(label='Let me set a time myself', value='custom'),
        ]
        last_selection = view.user_settings.reminder_claim_last_selection
        if last_selection > 0:
            options.insert(
                0,
                discord.SelectOption(label=f'{last_selection:g}h of production time', value=str(last_selection),
                                     emoji=emojis.REPEAT),
            )
        super().__init__(placeholder='Remind me after...', min_values=1, max_values=1, options=options, disabled=disabled,
                         row=row, custom_id='set_claim_reminder_time')

    async def callback(self, interaction: discord.Interaction):
        select_value = self.values[0]
        try:
            select_value = float(select_value)
        except ValueError:
            pass
        if isinstance(select_value, float):
            user_command = await functions.get_game_command(self.view.user_settings, 'claim')
            time_left = timedelta(hours=select_value)
            current_time = utils.utcnow()
            if self.view.user_settings.last_claim_time is None:
                await interaction.response.send_message(
                    (
                        f'I haven\'t recorded any claims yet. Please claim here I can see it next time.\n'
                        f'You can also manually set a claim time in '
                        f'{await functions.get_bot_slash_command(self.view.bot, "settings reminders")}.'
                    ),
                    ephemeral=True
                )
                await interaction.message.edit(view=self.view)
                return
            time_since_last_claim = current_time - self.view.user_settings.last_claim_time
            time_produced = (time_since_last_claim + (self.view.user_settings.time_speeders_used * timedelta(hours=2))
                             + (self.view.user_settings.time_compressors_used * timedelta(hours=4)))
            if time_left <= time_produced:
                await interaction.response.send_message(
                    (
                        f'I can\'t remind you after **{format_timespan(time_left)}** because your farms already '
                        f'produced **{format_timespan(time_produced - timedelta(microseconds=time_produced.microseconds))}** worth of materials.'
                    ),
                    ephemeral=True
                )
                await interaction.message.edit(view=self.view)
                return
            reminder_message = self.view.user_settings.reminder_claim.message.replace('{command}', user_command)
            reminder: reminders.Reminder = (
                await reminders.insert_user_reminder(self.view.user_settings.user_id, 'claim', time_left - time_produced,
                                                self.view.message.channel.id, reminder_message)
            )
            await self.view.user_settings.update(reminder_claim_last_selection=int(select_value))
            await interaction.response.send_message(
                (
                    f'Done. I will remind you when your farms have produced '
                    f'**{format_timespan(time_left)}** worth of materials.\n\n'
                    f'Time speeders and compressors will produce instantly and reduce reminder time accordingly.'
                ),
                ephemeral=True
            )
        else:
            modal = modals.SetClaimReminderTimeModal(self.view)
            await interaction.response.send_modal(modal)
            return
        await interaction.message.edit(view=self.view)


class SetClaimReminderTimeReminderList(discord.ui.Select):
    """Select to set the time of a claim reminder in the reminder list"""
    def __init__(self, view: discord.ui.View, disabled: Optional[bool] = False, row: Optional[int] = None):
        options = [
            discord.SelectOption(label='1h of production time', value='1'),
            discord.SelectOption(label='2h of production time', value='2'),
            discord.SelectOption(label='4h of production time', value='4'),
            discord.SelectOption(label='6h of production time', value='6'),
            discord.SelectOption(label='8h of production time', value='8'),
            discord.SelectOption(label='10h of production time', value='10'),
            discord.SelectOption(label='12h of production time', value='12'),
            discord.SelectOption(label='16h of production time', value='16'),
            discord.SelectOption(label='20h of production time', value='20'),
            discord.SelectOption(label='24h of production time', value='24'),
            discord.SelectOption(label='Let me set a time myself', value='custom'),
        ]
        last_selection = view.user_settings.reminder_claim_last_selection
        if last_selection > 0:
            options.insert(
                0,
                discord.SelectOption(label=f'{last_selection:g}h of production time', value=str(last_selection),
                                     emoji=emojis.REPEAT),
            )
        super().__init__(placeholder='Set claim reminder', min_values=1, max_values=1, options=options, disabled=disabled,
                         row=row, custom_id='set_claim_reminder_time')

    async def callback(self, interaction: discord.Interaction):
        select_value = self.values[0]
        try:
            select_value = float(select_value)
        except ValueError:
            pass
        if isinstance(select_value, float):
            user_command = await functions.get_game_command(self.view.user_settings, 'claim')
            time_left = timedelta(hours=select_value)
            current_time = utils.utcnow()
            time_since_last_claim = current_time - self.view.user_settings.last_claim_time
            time_produced = (time_since_last_claim + (self.view.user_settings.time_speeders_used * timedelta(hours=2))
                             + (self.view.user_settings.time_compressors_used * timedelta(hours=4)))
            if time_left <= time_produced:
                await interaction.response.send_message(
                    (
                        f'I can\'t remind you after **{format_timespan(time_left)}** because your farms already '
                        f'produced **{format_timespan(time_produced - timedelta(microseconds=time_produced.microseconds))}** '
                        f'worth of materials.'
                    ),
                    ephemeral=True
                )
                await interaction.message.edit(view=self.view)
                return
            reminder_message = self.view.user_settings.reminder_claim.message.replace('{command}', user_command)
            reminder: reminders.Reminder = (
                await reminders.insert_user_reminder(self.view.user_settings.user_id, 'claim', time_left - time_produced,
                                                self.view.message.channel.id, reminder_message)
            )
            await self.view.user_settings.update(reminder_claim_last_selection=int(select_value))
        else:
            modal = modals.SetClaimReminderTimeReminderListModal(self.view)
            await interaction.response.send_modal(modal)
            return
        embed = await self.view.embed_function(self.view.bot, self.view.user, self.view.user_settings,
                                               self.view.custom_reminders)
        await interaction.response.edit_message(embed=embed, view=self.view)


class SetDonorTierSelect(discord.ui.Select):
    """Select to set a donor tier"""
    def __init__(self, view: discord.ui.View, placeholder: str,
                 disabled: Optional[bool] = False, row: Optional[int] = None):
        options = []
        for index, donor_tier in enumerate(list(strings.DONOR_TIER_ENERGY_MULTIPLIERS.keys())):
            options.append(discord.SelectOption(label=f'{donor_tier.capitalize()}', value=str(index)))
        super().__init__(placeholder=placeholder, min_values=1, max_values=1, options=options, disabled=disabled,
                         row=row, custom_id=f'set_donor_tier')

    async def callback(self, interaction: discord.Interaction):
        select_value = self.values[0]
        await self.view.user_settings.update(donor_tier=int(select_value))
        embed = await self.view.embed_function(self.view.bot, self.view.ctx, self.view.user_settings)
        await interaction.response.edit_message(embed=embed, view=self.view)


class SetEnergyReminder(discord.ui.Select):
    """Select to set the an energy reminder"""
    def __init__(self, view: discord.ui.View, disabled: Optional[bool] = False, row: Optional[int] = None):
        options = [
            discord.SelectOption(label='Claim level (5)', value='5'),
            discord.SelectOption(label='Raid / Teamraid level (40)', value='40'),
            discord.SelectOption(label=f'Full energy ({view.user_settings.energy_max})',
                                 value=str(view.user_settings.energy_max)),
            discord.SelectOption(label='Custom amount', value='custom'),
            discord.SelectOption(label='Delete reminder', value='delete'),
        ]
        last_selection = view.user_settings.reminder_energy_last_selection
        if last_selection > 0:
            options.insert(
                0,
                discord.SelectOption(label=f'Last selected amount ({last_selection:g})', value=f'custom-{last_selection}',
                                     emoji=emojis.REPEAT),
            )
        super().__init__(placeholder='Set energy reminder', min_values=1, max_values=1, options=options, disabled=disabled,
                         row=row, custom_id='set_energy_reminder')

    async def callback(self, interaction: discord.Interaction):
        select_value = self.values[0]
        energy_regen_time = await functions.get_energy_regen_time(self.view.user_settings)
        try:
            energy_current = await functions.get_current_energy_amount(self.view.user_settings, energy_regen_time)
        except exceptions.EnergyFullTimeNoneError:
            await interaction.response.send_message(
                (
                    f'I can\'t set an energy reminder yet as you have never updated your energy.\n'
                    f'Please use {await functions.get_game_command(self.view.user_settings, "profile")} first.'
                ),
                ephemeral=True
            )
            await interaction.message.edit(view=self.view)
            return
        except exceptions.EnergyFullTimeOutdatedError:
            await interaction.response.send_message(
                (
                    f'You haven\'t updated your energy for too long.\n'
                    f'Please use {await functions.get_game_command(self.view.user_settings, "profile")} first.'
                ),
                ephemeral=True
            )
            await interaction.message.edit(view=self.view)
            return
        try:
            select_value = int(select_value.lstrip('custom-'))
        except ValueError:
            pass
        custom_reminders = getattr(self.view, 'custom_reminders', None)
        reminders_list_view = True if custom_reminders is not None else False
        if isinstance(select_value, int):
            if select_value <= energy_current:
                if energy_current == self.view.user_settings.energy_max:
                    answer_energy = f'You are already at max energy ({self.view.user_settings.energy_max}).'
                else:
                    answer_energy = (
                        f'Please enter a number between **{energy_current + 1}** and '
                        f'**{self.view.user_settings.energy_max}**'
                    )
                await interaction.response.send_message(
                    (
                        f'I can\'t remind you at an energy level you already reached.\n'
                        f'{answer_energy}'
                    ),
                    ephemeral=True
                )
                await interaction.message.edit(view=self.view)
                return
            energy_left = select_value - energy_current
            time_left = timedelta(seconds=energy_left * energy_regen_time.total_seconds())
            reminder: reminders.Reminder = (
                await reminders.insert_user_reminder(self.view.user_settings.user_id, f'energy-{select_value}',
                                                     time_left, self.view.message.channel.id,
                                                     self.view.user_settings.reminder_energy.message)
            )
            await self.view.user_settings.update(reminder_energy_last_selection=select_value)
            await interaction.response.send_message(
                (
                    f'Reminder set for `{select_value}` energy {utils.format_dt(reminder.end_time, "R")}.\n\n'
                    f'Please note that energy gained from `OHMMM` events is **not** tracked!\n'
                    f'If you join such an event, use {await functions.get_game_command(self.view.user_settings, "profile")} '
                    f'to update the reminder.\n'
                ),
                ephemeral=True
            )
        else:
            if select_value == 'custom':
                modal = modals.SetEnergyReminderModal(self.view, energy_current, energy_regen_time)
                await interaction.response.send_modal(modal)
                return
            if select_value == 'delete':
                try:
                    reminder: reminders.Reminder = await reminders.get_user_reminder(self.view.user.id, 'energy')
                    await reminder.delete()
                    if not reminders_list_view:
                        await interaction.response.send_message('Energy reminder deleted.', ephemeral=True)
                except exceptions.NoDataFoundError:
                    await interaction.response.send_message('No active energy reminder found.', ephemeral=True)
                    await interaction.message.edit(view=self.view)
                    return
            else:
                await interaction.response.send_message(
                    (
                        f'This is not a valid energy energy amount.\n'
                        f'Please enter a number between **{energy_current + 1}** and **{self.view.user_settings.energy_max}**'
                    ),
                    ephemeral=True
                )
                await interaction.message.edit(view=self.view)
                return
        custom_reminders = getattr(self.view, 'custom_reminders', None)
        if custom_reminders is not None:
            embed = await self.view.embed_function(self.view.bot, self.view.user, self.view.user_settings,
                                                   self.view.custom_reminders)
            if interaction.response.is_done():
                await interaction.message.edit(embed=embed, view=self.view)
            else:
                await interaction.response.edit_message(embed=embed, view=self.view)
        else:
            if interaction.response.is_done():
                await interaction.message.edit(view=self.view)
            else:
                await interaction.response.edit_message(view=self.view)


class ClanMembersViewSelect(discord.ui.Select):
    """Clan Members List Sort Select"""
    def __init__(self, row: Optional[int] = None):
        options = [
            discord.SelectOption(label='Top 3 power', value='0', emoji='💥'),
            discord.SelectOption(label='Guild seals', value='1', emoji=emojis.GUILD_SEAL),
        ]
        super().__init__(placeholder='Switch view ...', min_values=1, max_values=1, options=options, row=row,
                         custom_id='select_view')

    async def callback(self, interaction: discord.Interaction):
        self.view.current_view = int(self.values[0])
        embeds = await self.view.embed_function(self.view.clan_settings, self.view.current_view, self.view.sort_key)
        image = discord.MISSING
        if len(embeds) > 1:
            image = discord.File(settings.IMG_EMBED_WIDTH_LINE, filename='embed_width_line.png')
        for child in self.view.children:
            if child.custom_id == 'select_sort_key':
                options = []
                for sort_method, (sort_key, emoji) in self.view.sort_keys[self.view.current_view].items():
                    options.append(discord.SelectOption(label=sort_method, value=sort_key, emoji=emoji))
                child.options = options
                break
        await interaction.response.edit_message(embeds=embeds, view=self.view, file=image)


class ClanMembersViewSortSelect(discord.ui.Select):
    """Clan Members List Sort Select"""
    def __init__(self, view: discord.ui.View, sort_keys: Dict[int, Dict[str, str]], row: Optional[int] = None):
        self.sort_keys = sort_keys
        options = []
        for sort_method, (sort_key, emoji) in sort_keys[view.current_view].items():
            options.append(discord.SelectOption(label=sort_method, value=sort_key, emoji=emoji))
        super().__init__(placeholder='Sort by ...', min_values=1, max_values=1, options=options, row=row,
                         custom_id='select_sort_key')

    async def callback(self, interaction: discord.Interaction):
        self.view.sort_key = self.values[0]
        for child in self.view.children:
            if child.custom_id == 'select_sort_key':
                options = []
                for sort_method, (sort_key, emoji) in self.sort_keys[self.view.current_view].items():
                    options.append(discord.SelectOption(label=sort_method, value=sort_key, emoji=emoji))
                child.options = options
                break
        embeds = await self.view.embed_function(self.view.clan_settings, self.view.current_view, self.view.sort_key)
        image = discord.MISSING
        if len(embeds) > 1:
            image = discord.File(settings.IMG_EMBED_WIDTH_LINE, filename='embed_width_line.png')
        await interaction.response.edit_message(embeds=embeds, view=self.view, file=image)