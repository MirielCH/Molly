# modals.py

from datetime import timedelta
import random
import re
from typing import Literal

import discord
from discord import utils
from discord.ui import InputText, Modal
from humanfriendly import format_timespan

from database import reminders
from resources import exceptions, functions


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
        last_claim_time_old = self.view.user_settings.last_claim_time
        await self.view.user_settings.update(last_claim_time=last_claim_time, time_speeders_used=0, time_compressors_used=0)
        try:
            reminder: reminders.Reminder = await reminders.get_user_reminder(self.view.user.id, 'claim')
        except exceptions.NoDataFoundError:
            reminder = None
        if reminder is not None:
            original_reminder_time_left = reminder.end_time - last_claim_time_old
            new_end_time = self.view.user_settings.last_claim_time + original_reminder_time_left
            current_time = utils.utcnow()
            if new_end_time <= current_time: new_end_time = current_time + timedelta(seconds=1)
            await reminder.update(end_time=new_end_time)
        embed = await self.view.embed_function(self.view.bot, self.view.ctx, self.view.user_settings)
        await interaction.response.edit_message(embed=embed, view=self.view)
        await interaction.followup.send(
            content = (
                'Updated last claim time.\n'
                f'Note that if you had a claim reminder active, this also updated the reminder.'
            ),
            ephemeral =  True
        )
        

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
        time_produced = (time_since_last_claim + (self.view.user_settings.time_speeders_used * timedelta(hours=2))
                         + (self.view.user_settings.time_compressors_used * timedelta(hours=4)))
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
                f'Time speeders and compressors will produce instantly and reduce reminder time accordingly.'
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
        time_produced = (time_since_last_claim + (self.view.user_settings.time_speeders_used * timedelta(hours=2))
                         + (self.view.user_settings.time_compressors_used * timedelta(hours=4)))
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


# -- Energy reminder --
class SetEnergyReminderModal(Modal):
    def __init__(self, view: discord.ui.View, energy_current: int, energy_regen_time: timedelta) -> None:
        super().__init__(title='Set a custom energy reminder')
        self.view = view
        self.energy_current = energy_current
        self.energy_regen_time = energy_regen_time
        self.add_item(
            InputText(
                label='Energy to remind at:',
                placeholder='Example: 75',
            )
        )

    async def callback(self, interaction: discord.Interaction):
        energy = self.children[0].value
        try:
            energy = int(energy)
        except ValueError:
            await interaction.response.edit_message(view=self.view)
            await interaction.followup.send('That is not a valid number.', ephemeral=True)
            return
        
        if not self.energy_current < energy <= self.view.user_settings.energy_max:
            if self.energy_current == self.view.user_settings.energy_max:
                answer_energy = f'You are already at max energy ({self.view.user_settings.energy_max}).'
            else:
                answer_energy = (
                    f'Please enter a number between **{self.energy_current + 1}** and '
                    f'**{self.view.user_settings.energy_max}**'
                )
            await interaction.response.edit_message(view=self.view)
            await interaction.followup.send(
                (
                    f'I can\'t remind you at an energy level you already reached.\n'
                    f'{answer_energy}'
                ),
                ephemeral=True
            )
            return
        energy_left = energy - self.energy_current
        time_left = timedelta(seconds=energy_left * self.energy_regen_time.total_seconds())
        reminder: reminders.Reminder = (
            await reminders.insert_user_reminder(self.view.user_settings.user_id, f'energy-{energy}',
                                                 time_left, self.view.message.channel.id,
                                                 self.view.user_settings.reminder_energy.message)
        )
        await self.view.user_settings.update(reminder_energy_last_selection=energy)
        await interaction.response.send_message(
            (
                f'Reminder set for `{energy}` energy {utils.format_dt(reminder.end_time, "R")}.\n\n'
                f'Please note that energy gained from `OHMMM` events is **not** tracked!\n'
                f'If you join such an event, use {await functions.get_game_command(self.view.user_settings, "profile")} '
                f'to update the reminder.\n'
            ),
            ephemeral=True
        )
        custom_reminders = getattr(self.view, 'custom_reminders', None)
        if custom_reminders is not None:
            embed = await self.view.embed_function(self.view.bot, self.view.user, self.view.user_settings,
                                                   self.view.custom_reminders)
            await interaction.message.edit(embed=embed, view=self.view)
        else:
            await interaction.message.edit(view=self.view)


class SetClanReminderOffsetModal(Modal):
    def __init__(self, view: discord.ui.View) -> None:
        super().__init__(title='Set teamraid reminder offset')
        self.view = view
        self.add_item(
            InputText(
                label='Offset in hours:',
                placeholder='Example: 4.5 will shift the reminder to 04:30am UTC',
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
        if not 0 <= hours < 24:
            await interaction.response.edit_message(view=self.view)
            await interaction.followup.send('The offset needs to be at least 0 and less than 24 hours.', ephemeral=True)
            return
        await self.view.clan_settings.update(reminder_offset=hours)
        try:
            clan_reminder: reminders.Reminder = await reminders.get_clan_reminder(self.view.clan_settings.clan_name)
            current_time = utils.utcnow()
            midnight_today = utils.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
            end_time = midnight_today + timedelta(days=1, seconds=random.randint(60, 300))
            time_left = end_time - current_time + timedelta(hours=hours)
            await clan_reminder.update(end_time=current_time + time_left)
        except exceptions.NoDataFoundError:
            pass
        embed = await self.view.embed_function(self.view.bot, self.view.ctx, self.view.clan_settings)
        await interaction.response.edit_message(embed=embed, view=self.view)

        
class SetDailyReminderOffsetModal(Modal):
    def __init__(self, view: discord.ui.View) -> None:
        super().__init__(title='Set daily reminder offset')
        self.view = view
        self.add_item(
            InputText(
                label='Offset in hours:',
                placeholder='Example: 4.5 will shift reminders to 04:30am UTC',
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
        if not 0 <= hours < 24:
            await interaction.response.edit_message(view=self.view)
            await interaction.followup.send('The offset needs to be at least 0 and less than 24 hours.', ephemeral=True)
            return
        await self.view.user_settings.update(reminders_daily_offset=hours)
        try:
            daily_reminder: reminders.Reminder = await reminders.get_user_reminder(self.view.user.id, 'daily')
            current_time = utils.utcnow()
            midnight_today = utils.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
            end_time = midnight_today + timedelta(days=1, seconds=random.randint(60, 300))
            time_left = end_time - current_time + timedelta(hours=hours)
            await daily_reminder.update(end_time=current_time + time_left)
        except exceptions.NoDataFoundError:
            pass
        try:
            shop_reminders = await reminders.get_active_user_reminders(self.view.user.id, 'shop')
            current_time = utils.utcnow()
            midnight_today = utils.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
            end_time = midnight_today + timedelta(days=1, seconds=random.randint(60, 300))
            time_left = end_time - current_time + timedelta(hours=hours)
            for reminder in shop_reminders:
                await reminder.update(end_time=current_time + time_left)
        except exceptions.NoDataFoundError:
            pass
        embed = await self.view.embed_function(self.view.bot, self.view.ctx, self.view.user_settings)
        await interaction.response.edit_message(embed=embed, view=self.view)