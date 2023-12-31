# tracking.py
"""Provides access to the table "tracking_log" in the database"""


from dataclasses import dataclass
from datetime import datetime, timedelta
import sqlite3
from typing import NamedTuple, Optional, Tuple

from discord import utils

from database import errors
from resources import exceptions, settings, strings


# Containers
@dataclass()
class LogEntry():
    """Object that represents a record from table "tracking_log"."""
    amount: int
    text: str
    date_time: datetime
    entry_type: str
    guild_id: int
    user_id: int
    record_exists: bool = True

    async def delete(self) -> None:
        """Deletes the record from the database. Also calls refresh().

        Raises
        ------
        RecordExistsError if there was no error but the record was not deleted.
        """
        await _delete_log_entry(self)
        await self.refresh()
        if self.record_exists:
            error_message = f'Log entry got deleted but record still exists.\n{self}'
            await errors.log_error(error_message)
            raise exceptions.RecordExistsError(error_message)

    async def refresh(self) -> None:
        """Refreshes the log entry from the database.
        If the record doesn't exist anymore, "record_exists" will be set to False.
        All other values will stay on their old values before deletion (!).
        """
        try:
            new_settings = await get_log_entry(self.user_id, self.guild_id, self.text, self.date_time)
        except exceptions.NoDataFoundError as error:
            self.record_exists = False
            return
        self.amount = new_settings.amount
        self.text = new_settings.text
        self.entry_type = new_settings.entry_type
        self.date_time = new_settings.date_time
        self.guild_id = new_settings.guild_id
        self.user_id = new_settings.user_id

    async def update(self, **kwargs) -> None:
        """Updates the log entry record in the database. Also calls refresh().

        Arguments
        ---------
        kwargs (column=value):
            amount: int
            text: str
            date_time: datetime
            entry_type: Literal['single', 'summary']
            guild_id: int
        """
        await _update_log_entry(self, **kwargs)
        await self.refresh()

class LogReport(NamedTuple):
    """Object that represents a report based on a certain amount of log entries."""
    guild_id: int # Set to None if no guild_id was provided
    raid_amount: int
    roll_amount: int
    raid_points_gained: str
    raid_points_lost: int
    timeframe: timedelta
    workers: dict
    user_id: int


# Miscellaneous functions
async def _dict_to_log_entry(record: dict) -> LogEntry:
    """Creates a LogEntry object from a database record

    Arguments
    ---------
    record: Database record from table "tracking_log" as a dict.

    Returns
    -------
    LogEntry object.

    Raises
    ------
    LookupError if something goes wrong reading the dict. Also logs this error to the database.
    """
    function_name = '_dict_to_log_entry'
    try:
        log_entry = LogEntry(
            amount = record['amount'],
            text = record['text'],
            date_time = datetime.fromisoformat(record['date_time']),
            entry_type = record['type'],
            guild_id = record['guild_id'],
            user_id = record['user_id'],
        )
    except Exception as error:
        await errors.log_error(
            strings.INTERNAL_ERROR_DICT_TO_OBJECT.format(function=function_name, record=record)
        )
        raise LookupError(error)

    return log_entry


# Read Data
async def get_log_entry(user_id: int, guild_id: int, text: str, date_time: datetime,
                        entry_type: Optional[str] = 'single') -> LogEntry:
    """Gets a specific log entry based on a specific user, command and an EXACT time.
    Since the exact time is usually unknown, this is mostly used for refreshing an object.

    Returns
    -------
    LogEntry

    Raises
    ------
    sqlite3.Error if something happened within the database.
    exceptions.NoDataFoundError if no guild was found.
    LookupError if something goes wrong reading the dict.
    Also logs all errors to the database.
    """
    table = 'tracking_log'
    function_name = 'get_log_entry'
    sql = f'SELECT * FROM {table} WHERE user_id=? AND guild_id=? AND text=? AND date_time=? AND type=?'
    try:
        cur = settings.DATABASE.cursor()
        cur.execute(sql, (user_id, guild_id, text, date_time, entry_type))
        record = cur.fetchone()
    except sqlite3.Error as error:
        await errors.log_error(
            strings.INTERNAL_ERROR_SQLITE3.format(error=error, table=table, function=function_name, sql=sql)
        )
        raise
    if not record:
        raise exceptions.NoDataFoundError(
            f'No log data found in database for user "{user_id}", text "{text}" '
            f'and time "{str(datetime)}".'
        )
    log_entry = await _dict_to_log_entry(dict(record))

    return log_entry


async def get_log_entries(user_id: int, text: str, timeframe: timedelta,
                          guild_id: Optional[int] = None) -> Tuple[LogEntry]:
    """Gets all log entries for one command for a certain amount of time from a user id.
    If the guild_id is specified, the log entries are limited to that guild.

    Arguments
    ---------
    user_id: int
    text: str
    timeframe: timedelta object with the amount of time that should be covered, starting from UTC now
    guild_id: Optional[int]

    Returns
    -------
    Tuple[LogEntry]

    Raises
    ------
    sqlite3.Error if something happened within the database.
    exceptions.NoDataFoundError if no guild was found.
    LookupError if something goes wrong reading the dict.
    Also logs all errors to the database.
    """
    table = 'tracking_log'
    function_name = 'get_log_entries'
    sql = (
        f'SELECT * FROM {table} WHERE user_id=? AND date_time>=? AND text=?'
    )
    date_time = utils.utcnow() - timeframe
    if guild_id is not None: sql = f'{sql} AND guild_id=?'
    try:
        cur = settings.DATABASE.cursor()
        if guild_id is None:
            cur.execute(sql, (user_id, date_time, text))
        else:
            cur.execute(sql, (user_id, date_time, text, guild_id))
        records = cur.fetchall()
    except sqlite3.Error as error:
        await errors.log_error(
            strings.INTERNAL_ERROR_SQLITE3.format(error=error, table=table, function=function_name, sql=sql)
        )
        raise
    if not records:
        error_message = f'No log data found in database for timeframe "{str(timeframe)}".'
        if guild_id is not None: error_message = f'{error_message} Guild: {guild_id}'
        raise exceptions.NoDataFoundError(error_message)
    log_entries = []
    for record in records:
        log_entry = await _dict_to_log_entry(dict(record))
        log_entries.append(log_entry)

    return tuple(log_entries)


async def get_all_log_entries(user_id: int) -> Tuple[LogEntry]:
    """Gets ALL log entries for a user.

    Arguments
    ---------
    user_id: int

    Returns
    -------
    Tuple[LogEntry]

    Raises
    ------
    sqlite3.Error if something happened within the database.
    exceptions.NoDataFoundError if no guild was found.
    LookupError if something goes wrong reading the dict.
    Also logs all errors to the database.
    """
    table = 'tracking_log'
    function_name = 'get_all_log_entries'
    sql = (
        f'SELECT * FROM {table} WHERE user_id=?'
    )
    try:
        cur = settings.DATABASE.cursor()
        cur.execute(sql, (user_id,))
        records = cur.fetchall()
    except sqlite3.Error as error:
        await errors.log_error(
            strings.INTERNAL_ERROR_SQLITE3.format(error=error, table=table, function=function_name, sql=sql)
        )
        raise
    if not records:
        error_message = f'No log data found in database for user {user_id}".'
        raise exceptions.NoDataFoundError(error_message)
    log_entries = []
    for record in records:
        log_entry = await _dict_to_log_entry(dict(record))
        log_entries.append(log_entry)

    return tuple(log_entries)


async def get_old_log_entries(days: int) -> Tuple[LogEntry]:
    """Gets all single log entries older than a certain amount of days.

    Arguments
    ---------
    user_id: int
    days: amount of days that should be kept as single entries
    guild_id: Optional[int]

    Returns
    -------
    Tuple[LogEntry]

    Raises
    ------
    sqlite3.Error if something happened within the database.
    exceptions.NoDataFoundError if no guild was found.
    LookupError if something goes wrong reading the dict.
    Also logs all errors to the database.
    """
    table = 'tracking_log'
    function_name = 'get_old_log_entries'
    sql = (
        f'SELECT * FROM {table} WHERE date_time<? AND type=?'
    )
    date_time = utils.utcnow() - timedelta(days=days)
    date_time = date_time.replace(hour=0, minute=0, second=0)
    try:
        cur = settings.DATABASE.cursor()
        cur.execute(sql, (date_time, 'single'))
        records = cur.fetchall()
    except sqlite3.Error as error:
        await errors.log_error(
            strings.INTERNAL_ERROR_SQLITE3.format(error=error, table=table, function=function_name, sql=sql)
        )
        raise
    if not records:
        error_message = f'No log data found in database older than {days} days".'
        raise exceptions.NoDataFoundError(error_message)
    log_entries = []
    for record in records:
        log_entry = await _dict_to_log_entry(dict(record))
        log_entries.append(log_entry)

    return tuple(log_entries)


async def get_log_report(user_id: int, timeframe: timedelta,
                         guild_id: Optional[int] = None) -> LogReport:
    """Gets a summary log report for all commands for a certain amount of time from a user id.
    If the guild_id is specified, the report is limited to that guild.

    Returns
    -------
    LogReport object

    Raises
    ------
    sqlite3.Error if something happened within the database.
    LookupError if something goes wrong reading the dict.
    Also logs all errors to the database.
    """
    table = 'tracking_log'
    function_name = 'get_log_report'
    sql = f'SELECT text, SUM(amount) FROM {table} WHERE user_id=? AND date_time>=?'
    date_time = datetime.utcnow() - timeframe
    if guild_id is not None: sql = f'{sql} AND guild_id=?'
    sql = f'{sql} GROUP BY text'
    try:
        cur = settings.DATABASE.cursor()
        if guild_id is None:
            cur.execute(sql, (user_id, date_time))
        else:
            cur.execute(sql, (user_id, date_time, guild_id))
        records = cur.fetchall()
    except sqlite3.Error as error:
        await errors.log_error(
            strings.INTERNAL_ERROR_SQLITE3.format(error=error, table=table, function=function_name, sql=sql)
        )
        raise
    if timeframe.days > 28:
        raid_amount = -1
    else:
        sql = f'SELECT COUNT(*) FROM {table} WHERE user_id=? AND date_time>=? AND (text=? OR text=?)'
        try:
            cur = settings.DATABASE.cursor()
            cur.execute(sql, (user_id, date_time, 'raid-points-gained', 'raid-points-lost'))
            record_raid_amount = cur.fetchone()
        except sqlite3.Error as error:
            await errors.log_error(
                strings.INTERNAL_ERROR_SQLITE3.format(error=error, table=table, function=function_name, sql=sql)
            )
            raise
        (raid_amount,) = record_raid_amount
    records_data = {
        'raid-points-gained': 0,
        'raid-points-lost': 0,
    }
    workers = {}
    roll_amount = 0
    for worker_type in strings.WORKER_TYPES:
        workers[worker_type] = 0
    for record in records:
        record = dict(record)
        if record['text'].startswith('worker'):
            workers[record['text'][7:]] = record['SUM(amount)']
            roll_amount += record['SUM(amount)']
        else:
            records_data[record['text']] = record['SUM(amount)']
    log_report = LogReport(
        raid_amount = raid_amount,
        raid_points_gained = records_data['raid-points-gained'],
        raid_points_lost = records_data['raid-points-lost'],
        roll_amount = roll_amount,
        workers = workers,
        guild_id = guild_id,
        timeframe = timeframe,
        user_id = user_id,
    )
    return log_report


# Write Data
async def _delete_log_entry(log_entry: LogEntry) -> None:
    """Deletes a log entry. Use LogEntry.delete() to trigger this function.

    Raises
    ------
    sqlite3.Error if something happened within the database.
    NoArgumentsError if no kwargs are passed (need to pass at least one)
    Also logs all errors to the database.
    """
    table = 'tracking_log'
    function_name = '_delete_log_entry'
    sql = f'DELETE FROM {table} WHERE user_id=? AND guild_id=? AND text=? AND date_time=? AND type=?'
    try:
        cur = settings.DATABASE.cursor()
        cur.execute(sql, (log_entry.user_id, log_entry.guild_id, log_entry.text, log_entry.date_time,
                          log_entry.entry_type))
    except sqlite3.Error as error:
        await errors.log_error(
            strings.INTERNAL_ERROR_SQLITE3.format(error=error, table=table, function=function_name, sql=sql)
        )
        raise


async def _update_log_entry(log_entry: LogEntry, **kwargs) -> None:
    """Updates tracking_log record. Use LogEntry.update() to trigger this function.

    Arguments
    ---------
    user_id: int
    kwargs (column=value):
        amount: int
        text: str
        date_time: datetime
        entry_type: Literal['single', 'summary']
        guild_id: int
        user_id: int

    Raises
    ------
    sqlite3.Error if something happened within the database.
    NoArgumentsError if no kwargs are passed (need to pass at least one)
    Also logs all errors to the database.
    """
    table = 'tracking_log'
    function_name = '_update_log_entry'
    if not kwargs:
        await errors.log_error(
            strings.INTERNAL_ERROR_NO_ARGUMENTS.format(table=table, function=function_name)
        )
        raise exceptions.NoArgumentsError('You need to specify at least one keyword argument.')
    try:
        cur = settings.DATABASE.cursor()
        sql = f'UPDATE {table} SET'
        for kwarg in kwargs:
            sql = f'{sql} {kwarg} = :{kwarg},'
        sql = sql.strip(",")
        kwargs['user_id_old'] = log_entry.user_id
        kwargs['text_old'] = log_entry.text
        kwargs['date_time_old'] = log_entry.date_time
        kwargs['entry_type_old'] = log_entry.entry_type
        sql = (
            f'{sql} WHERE user_id = :user_id_old AND type = :entry_type_old AND text = :text_old '
            f'AND date_time = :date_time_old'
        )
        cur.execute(sql, kwargs)
    except sqlite3.Error as error:
        await errors.log_error(
            strings.INTERNAL_ERROR_SQLITE3.format(error=error, table=table, function=function_name, sql=sql)
        )
        raise


async def insert_log_entry(user_id: int, guild_id: int,
                           text: str, date_time: datetime, amount: Optional[int] = 1) -> LogEntry:
    """Inserts a single record to the table "tracking_log".

    Returns
    -------
    LogEntry object with the newly created log entry.

    Raises
    ------
    sqlite3.Error if something happened within the database.
    Also logs all errors to the database.
    """
    function_name = 'insert_log_entry'
    table = 'tracking_log'
    sql = (
        f'INSERT INTO {table} (user_id, guild_id, text, amount, date_time) VALUES (?, ?, ?, ?, ?)'
    )
    try:
        cur = settings.DATABASE.cursor()
        cur.execute(sql, (user_id, guild_id, text, amount, date_time))
    except sqlite3.Error as error:
        await errors.log_error(
            strings.INTERNAL_ERROR_SQLITE3.format(error=error, table=table, function=function_name, sql=sql)
        )
        raise
    log_entry = await get_log_entry(user_id, guild_id, text, date_time)

    return log_entry


async def insert_log_summary(user_id: int, guild_id: int, text: str, date_time: datetime,
                             amount: int) -> LogEntry:
    """Inserts a summary record to the table "tracking_log". If record already exists, count is increased by one instead.

    Returns
    -------
    LogEntry object with the newly created log entry.

    Raises
    ------
    sqlite3.Error if something happened within the database.
    Also logs all errors to the database.
    """
    function_name = 'insert_log_summary'
    table = 'tracking_log'
    log_entry = None
    try:
        log_entry = await get_log_entry(user_id, guild_id, text, date_time, 'summary')
    except exceptions.NoDataFoundError:
        pass
    if log_entry is not None:
        await log_entry.update(amount=log_entry.amount + amount)
    else:
        sql = (
            f'INSERT INTO {table} (user_id, guild_id, text, amount, date_time, type) VALUES (?, ?, ?, ?, ?, ?)'
        )
        try:
            cur = settings.DATABASE.cursor()
            cur.execute(sql, (user_id, guild_id, text, amount, date_time, 'summary'))
        except sqlite3.Error as error:
            await errors.log_error(
                strings.INTERNAL_ERROR_SQLITE3.format(error=error, table=table, function=function_name, sql=sql)
            )
            raise
        log_entry = await get_log_entry(user_id, guild_id, text, date_time, 'summary')

    return log_entry


async def delete_log_entries(user_id: int, guild_id: int, text: str, date_time_min: datetime,
                             date_time_max: datetime) -> None:
    """Deletes all single log entries between two datetimes.

    Raises
    ------
    sqlite3.Error if something happened within the database.
    NoArgumentsError if no kwargs are passed (need to pass at least one)
    Also logs all errors to the database.
    """
    table = 'tracking_log'
    function_name = '_delete_log_entries'
    sql = f'DELETE FROM {table} WHERE user_id=? AND guild_id=? AND text=? AND type=? AND date_time BETWEEN ? AND ?'
    try:
        cur = settings.DATABASE.cursor()
        cur.execute(sql, (user_id, guild_id, text, 'single', date_time_min, date_time_max))
    except sqlite3.Error as error:
        await errors.log_error(
            strings.INTERNAL_ERROR_SQLITE3.format(error=error, table=table, function=function_name, sql=sql)
        )
        raise