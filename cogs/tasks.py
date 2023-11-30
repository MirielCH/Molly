# tasks.py
"""Contains task related stuff"""

import asyncio
from datetime import timedelta
from humanfriendly import format_timespan
import sqlite3

import discord
from discord import utils
from discord.ext import commands, tasks

from cache import messages
from database import clans, errors, reminders, tracking, users
from resources import exceptions, functions, logs, settings


running_tasks = {}


class TasksCog(commands.Cog):
    """Cog with tasks"""
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # Task management
    async def background_task(self, reminder: reminders.Reminder) -> None:
        """Background task for scheduling reminders"""
        current_time = utils.utcnow().replace(microsecond=0)
        def get_time_left() -> timedelta:
            time_left = reminder.end_time - current_time
            if time_left.total_seconds() < 0: time_left = timedelta(seconds=0)
            return time_left
        
        try:
            if reminder.activity != 'clan':
                user = await functions.get_discord_user(self.bot, reminder.user_id)
                user_settings = await users.get_user(user.id)
                if user_settings.reminder_channel_id is not None:
                    channel_id = user_settings.reminder_channel_id
                else:
                    channel_id = reminder.channel_id
                channel = await functions.get_discord_channel(self.bot, channel_id)
                if channel is None: return
                message_content = embed = None
                if reminder.activity == 'custom':
                    reminder_message = user_settings.reminder_custom.message.replace('{custom_reminder_text}', reminder.message)
                else:
                    reminder_message = reminder.message
                if not user_settings.dnd_mode_enabled:
                    if user_settings.reminders_as_embed:
                        message_content = user.mention
                        reminder_message = reminder_message.replace("{name}", user.display_name)
                    else:
                        reminder_message = reminder_message.replace("{name}", user.mention)
                else:
                    reminder_message = reminder_message.replace("{name}", user.display_name)
                if reminder.activity == 'claim':
                    reminder_message = reminder_message.replace(
                        '{last_claim_time}',
                        utils.format_dt(user_settings.last_claim_time, "R")
                    )
                    production_time = (
                        reminder.end_time
                        - user_settings.last_claim_time
                        + (user_settings.time_speeders_used * timedelta(hours=2))
                        + (user_settings.time_compressors_used * timedelta(hours=4))
                    )
                    microseconds = production_time.microseconds
                    production_time = production_time - timedelta(microseconds=production_time.microseconds)
                    if microseconds >= 500_000: production_time += timedelta(seconds=1)
                    reminder_message = reminder_message.replace('{production_time}', format_timespan(production_time))
                if reminder.activity.startswith('energy'):
                    reminder_message = (
                        reminder_message
                        .replace('{energy_amount}', reminder.activity[7:])
                        .replace('{energy_full_time}', utils.format_dt(user_settings.energy_full_time, 'R'))
                    )
                if user_settings.reminders_as_embed:
                    description = ''
                    for index, line in enumerate(reminder_message.split('\n'), 1):
                        if index == 1:
                            title = line.strip()
                        else:
                            description = f'{description}\n{line}'
                    embed = discord.Embed(
                        color = settings.EMBED_COLOR,
                        title = title,
                        description = description
                    )
                else:
                    message_content = reminder_message.strip()
                time_left = get_time_left()
                try:
                    await asyncio.sleep(time_left.total_seconds())
                    allowed_mentions = discord.AllowedMentions(users=[user,])
                    await channel.send(content=message_content, embed=embed, allowed_mentions=allowed_mentions)
                except asyncio.CancelledError:
                    return
                except discord.errors.Forbidden:
                    return
            if reminder.activity == 'clan':
                clan_settings = await clans.get_clan_by_clan_name(reminder.clan_name)
                channel = await functions.get_discord_channel(self.bot, clan_settings.reminder_channel_id)
                if channel is None: return
                reminder_message = reminder.message.replace('{guild_role}', f'<@&{clan_settings.reminder_role_id}>')
                time_left = get_time_left()
                try:
                    await asyncio.sleep(time_left.total_seconds())
                    allowed_mentions = discord.AllowedMentions(roles=True)
                    await channel.send(reminder_message, allowed_mentions=allowed_mentions)
                except asyncio.CancelledError:
                    return
                except discord.errors.Forbidden:
                    return                
            running_tasks.pop(reminder.task_name, None)
        except discord.errors.Forbidden:
            return
        except Exception as error:
            await errors.log_error(error)

    async def create_task(self, reminder: reminders.Reminder) -> None:
        """Creates a new background task"""
        await self.delete_task(reminder.task_name)
        task = self.bot.loop.create_task(self.background_task(reminder))
        running_tasks[reminder.task_name] = task

    async def delete_task(self, task_name: str) -> None:
        """Stops and deletes a running task if it exists"""
        if task_name in running_tasks:
            running_tasks[task_name].cancel()
            running_tasks.pop(task_name, None)
        return

    # Events
    @commands.Cog.listener()
    async def on_ready(self) -> None:
        """Fires when bot has finished starting"""
        reminders.schedule_reminders.start()
        self.delete_old_reminders.start()
        self.schedule_tasks.start()
        self.consolidate_tracking_log.start()
        self.delete_old_messages_from_cache.start()

    # Tasks
    @tasks.loop(seconds=0.5)
    async def schedule_tasks(self):
        """Task that creates or deletes tasks from scheduled reminders.
        Reminders that fire at the same second for the same user in the same channel are combined into one task.
        """
        for reminder in reminders.scheduled_for_deletion.copy().values():
            reminders.scheduled_for_deletion.pop(reminder.task_name, None)
            await self.delete_task(reminder.task_name)
        for reminder in reminders.scheduled_for_tasks.copy().values():
            reminders.scheduled_for_tasks.pop(reminder.task_name, None)
            await self.create_task(reminder)

    @tasks.loop(minutes=2.0)
    async def delete_old_reminders(self) -> None:
        """Task that deletes all old reminders"""
        try:
            old_user_reminders = await reminders.get_old_user_reminders()
        except:
            old_user_reminders = ()
        try:
            old_clan_reminders = await reminders.get_old_clan_reminders()
        except:
            old_clan_reminders = ()
        old_reminders = list(old_user_reminders) + list(old_clan_reminders)
        for reminder in old_reminders:
            try:
                await reminder.delete()
            except Exception as error:
                await errors.log_error(
                    f'Error deleting old reminder.\nFunction: delete_old_reminders\n'
                    f'Reminder: {reminder}\nError: {error}'
            )

    @tasks.loop(seconds=60)
    async def consolidate_tracking_log(self) -> None:
        """Task that consolidates tracking log entries older than 28 days into summaries"""
        start_time = utils.utcnow().replace(microsecond=0)
        if start_time.hour == 0 and start_time.minute == 0:
            log_entry_count = 0
            try:
                old_log_entries = await tracking.get_old_log_entries(28)
            except exceptions.NoDataFoundError:
                logs.logger.info('Didn\'t find any log entries to consolidate.')
                return
            entries = {}
            for log_entry in old_log_entries:
                date_time = log_entry.date_time.replace(hour=23, minute=59, second=59, microsecond=999999)
                key = (log_entry.user_id, log_entry.guild_id, log_entry.text, date_time)
                amount = entries.get(key, 0)
                entries[key] = amount + log_entry.amount
                log_entry_count += 1
            for key, amount in entries.items():
                user_id, guild_id, command, date_time = key
                summary_log_entry = await tracking.insert_log_summary(user_id, guild_id, command, date_time, amount)
                date_time_min = date_time.replace(hour=0, minute=0, second=0, microsecond=0)
                date_time_max = date_time.replace(hour=23, minute=59, second=59, microsecond=999999)
                await tracking.delete_log_entries(user_id, guild_id, command, date_time_min, date_time_max)
                await asyncio.sleep(0.01)
            cur = settings.DATABASE.cursor()
            date_time = utils.utcnow() - timedelta(days=366)
            date_time = date_time.replace(hour=0, minute=0, second=0)
            sql = 'DELETE FROM tracking_log WHERE date_time<?'
            try:
                cur.execute(sql, (date_time,))
                cur.execute('VACUUM')
            except sqlite3.Error as error:
                logs.logger.error(f'Error while consolidating: {error}')
                raise
            end_time = utils.utcnow().replace(microsecond=0)
            time_passed = end_time - start_time
            logs.logger.info(f'Consolidated {log_entry_count:,} log entries in {format_timespan(time_passed)}.')

    @tasks.loop(minutes=10)
    async def delete_old_messages_from_cache(self) -> None:
        """Task that deletes messages from the message cache that are older than 10 minutes"""
        deleted_messages_count = await messages.delete_old_messages(timedelta(minutes=10))
        if settings.DEBUG_MODE:
            logs.logger.debug(f'Deleted {deleted_messages_count} messages from message cache.')

# Initialization
def setup(bot):
    bot.add_cog(TasksCog(bot))