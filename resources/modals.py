# modals.py

from datetime import timedelta
import re
from typing import Literal

import discord
from discord import utils
from discord.ui import InputText, Modal
from humanfriendly import format_timespan

from database import reminders
from resources import functions


# --- Settings: Server ---
class SetPrefixModal(Modal):
    def __init__(self, view: discord.ui.View) -> None:
        super().__init__(title='Change prefix')
        self.view = view
        self.add_item(
            InputText(
                label='New prefix:',
                placeholder="Enter prefix ...",
            )
        )

    async def callback(self, interaction: discord.Interaction):
        new_prefix = self.children[0].value.strip('"')
        await self.view.guild_settings.update(prefix=new_prefix)
        embed = await self.view.embed_function(self.view.bot, self.view.ctx, self.view.guild_settings)
        await interaction.response.edit_message(embed=embed, view=self.view)


# --- Settings: Reminders ---
class SetLastClaimModal(Modal):
    def __init__(self, view: discord.ui.View) -> None:
        super().__init__(title='Change last claim time')
        self.view = view
        self.add_item(
            InputText(
                label='Message ID or link of your last claim:',
                placeholder="Enter message ID or link ..."
            )
        )

    async def callback(self, interaction: discord.Interaction):
        msg_error = (
            f'No valid message ID or URL found.\n\n'
            f'Use the ID or link of the message that shows your claimed items.\n'
            f'If you don\'t have access to that message, choose another message that is as close '
            f'to your last claim as possible.\n'
            f'Note that it does not matter if I can actually read the message, I only need the ID or link.'
        )
        message_id_link = self.children[0].value.lower()
        if 'discord.com/channels' in message_id_link:
            message_id_match = re.search(r"\/[0-9]+\/[0-9]+\/(.+?)$", message_id_link)
            if message_id_match:
                message_id = message_id_match.group(1)
            else:
                await interaction.response.edit_message(view=self.view)
                await interaction.followup.send(msg_error, ephemeral=True)
                return
        else:
            message_id = message_id_link
        try:
            last_claim_time = utils.snowflake_time(int(message_id)).replace(microsecond=0)
        except:
            await interaction.response.edit_message(view=self.view)
            await interaction.followup.send(msg_error, ephemeral=True)
            return
        await self.view.user_settings.update(last_claim_time=last_claim_time, time_speeders_used=0)
        embed = await self.view.embed_function(self.view.bot, self.view.ctx, self.view.user_settings)
        await interaction.response.edit_message(embed=embed, view=self.view)


# -- Dev ---
class SetEventReductionModal(Modal):
    def __init__(self, view: discord.ui.View, activity: str, cd_type: Literal['slash', 'text']) -> None:
        titles = {
            'slash': 'Change slash event reduction',
            'text': 'Change text event reduction',
        }
        labels = {
            'slash': 'Event reduction in percent:',
            'text': 'Event reduction in percent:',
        }
        placeholders = {
            'slash': 'Enter event reduction...',
            'text': 'Enter event reduction...',
        }
        super().__init__(title=titles[cd_type])
        self.view = view
        self.activity = activity
        self.cd_type = cd_type
        self.add_item(
            InputText(
                label=labels[cd_type],
                placeholder=placeholders[cd_type],
            )
        )

    async def callback(self, interaction: discord.Interaction):
        new_value = self.children[0].value
        try:
            new_value = float(new_value)
        except ValueError:
            await interaction.response.edit_message(view=self.view)
            await interaction.followup.send('That is not a valid number.', ephemeral=True)
            return
        if not 0 <= new_value <= 100:
            await interaction.response.edit_message(view=self.view)
            await interaction.followup.send('The reduction needs to be between 0 and 100 percent.', ephemeral=True)
            return
        if self.activity == 'all':
            for cooldown in self.view.all_cooldowns:
                if self.cd_type == 'slash':
                    await cooldown.update(event_reduction_slash=new_value)
                else:
                    await cooldown.update(event_reduction_mention=new_value)
        else:
            for cooldown in self.view.all_cooldowns:
                if cooldown.activity == self.activity:
                    if self.cd_type == 'slash':
                        await cooldown.update(event_reduction_slash=new_value)
                    else:
                        await cooldown.update(event_reduction_mention=new_value)
        embed = await self.view.embed_function(self.view.all_cooldowns)
        await interaction.response.edit_message(embed=embed, view=self.view)


# -- Claim reminder --
class SetClaimReminderTimeModal(Modal):
    def __init__(self, view: discord.ui.View) -> None:
        super().__init__(title='Set custom claim reminder time')
        self.view = view
        self.add_item(
            InputText(
                label='Farm production time in hours:',
                placeholder='Example: 2 or 4.5',
            )
        )

    async def callback(self, interaction: discord.Interaction):
        hours = self.children[0].value
        try:
            hours = float(hours)
        except ValueError:
            await interaction.response.edit_message(view=self.view)
            await interaction.followup.send('That is not a valid number.', ephemeral=True)
            return
        if not 0 < hours <= 24:
            await interaction.response.edit_message(view=self.view)
            await interaction.followup.send('The production time needs to be between 0 and 24 hours.', ephemeral=True)
            return
        user_command = await functions.get_game_command(self.view.user_settings, 'claim')
        time_left = timedelta(hours=hours)
        current_time = utils.utcnow()
        time_since_last_claim = current_time - self.view.user_settings.last_claim_time
        time_produced = time_since_last_claim + self.view.user_settings.time_speeders_used * timedelta(hours=2)
        if time_left <= time_produced:
            await interaction.response.edit_message(view=self.view)
            await interaction.followup.send(
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
        await self.view.user_settings.update(reminder_claim_last_selection=hours)
        await interaction.response.send_message(
            (
                f'Done! I will remind you when your farms have produced '
                f'**{format_timespan(time_left)}** worth of materials.\n\n'
                f'Time speeders will produce 2 hours instantly and reduce reminder time accordingly.'
            ),
            ephemeral=True
        )
        await interaction.message.edit(view=self.view)

        
class SetClaimReminderTimeReminderListModal(Modal):
    def __init__(self, view: discord.ui.View) -> None:
        super().__init__(title='Set custom claim reminder time')
        self.view = view
        self.add_item(
            InputText(
                label='Farm production time in hours:',
                placeholder='Example: 2 or 4.5',
            )
        )

    async def callback(self, interaction: discord.Interaction):
        hours = self.children[0].value
        try:
            hours = float(hours)
        except ValueError:
            await interaction.response.edit_message(view=self.view)
            await interaction.followup.send('That is not a valid number.', ephemeral=True)
            return
        if not 0 < hours <= 24:
            await interaction.response.edit_message(view=self.view)
            await interaction.followup.send('The production time needs to be between 0 and 24 hours.', ephemeral=True)
            return
        user_command = await functions.get_game_command(self.view.user_settings, 'claim')
        time_left = timedelta(hours=hours)
        current_time = utils.utcnow()
        time_since_last_claim = current_time - self.view.user_settings.last_claim_time
        time_produced = time_since_last_claim + self.view.user_settings.time_speeders_used * timedelta(hours=2)
        if time_left <= time_produced:
            await interaction.response.edit_message(view=self.view)
            await interaction.followup.send(
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
        await self.view.user_settings.update(reminder_claim_last_selection=hours)
        embed = await self.view.embed_function(self.view.bot, self.view.user, self.view.user_settings, 
                                               self.view.custom_reminders)
        await interaction.response.edit_message(embed=embed, view=self.view)