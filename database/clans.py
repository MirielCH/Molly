# clans.py
"""Provides access to the tables "clans" and "clan_members" in the database"""


from dataclasses import dataclass
import sqlite3
from typing import List, Tuple, Union

from database import errors
from resources import exceptions, settings, strings


# Containers
@dataclass()
class Clan():
    """Object that represents a record from table "clans"."""
    clan_name: str
    leader_id: int
    member_ids: Tuple[int]
    reminder_channel_id: int
    reminder_enabled: bool
    reminder_message: str
    reminder_role_id: int
    record_exists: bool = True

    async def delete(self) -> None:
        """Deletes the clan record from the database. Also calls refresh().

        Raises
        ------
        RecordExistsError if there was no error but the record was not deleted.
        """
        await _delete_clan(self)
        await self.refresh()
        if self.record_exists:
            error_message = f'Clan got deleted but record still exists.\n{self}'
            await errors.log_error(error_message)
            raise exceptions.RecordExistsError(error_message)

    async def refresh(self) -> None:
        """Refreshes clan data from the database.
        If the record doesn't exist anymore, "record_exists" will be set to False.
        All other values will stay on their old values before deletion (!).
        """
        new_settings = await get_clan_by_clan_name(self.clan_name)
        self.leader_id = new_settings.leader_id
        self.member_ids = new_settings.member_ids
        self.reminder_channel_id = new_settings.reminder_channel_id
        self.reminder_enabled = new_settings.reminder_enabled
        self.reminder_message = new_settings.reminder_message
        self.reminder_role_id = new_settings.reminder_role_id

    async def update(self, **kwargs) -> None:
        """Updates the clan record in the database. Also calls refresh().

        Arguments
        ---------
        kwargs (column=value):
            clan_name: str
            leader_id: int
            member_ids: Union[Tuple[int],List[int]] (up to 50)
            reminder_channel_id: int
            reminder_enabled: bool
            reminder_message: str
            reminder_role_id: int

        Raises
        ------
        sqlite3.Error if something happened within the database.
        NoArgumentsError if no kwargs are passed (need to pass at least one)
        Also logs all errors to the database.
        """
        await _update_clan(self, **kwargs)
        await self.refresh()


# Miscellaneous functions
async def _dict_to_clan(record: dict) -> Clan:
    """Creates a Clan object from a database record

    Arguments
    ---------
    record: Database record from table "clans" as a dict.

    Returns
    -------
    Clan object.

    Raises
    ------
    LookupError if something goes wrong reading the dict. Also logs this error to the database.
    """
    function_name = '_dict_to_clan'
    clan_name = record['clan_name']
    try:
        clan_member_ids = await get_clan_member_ids(record['clan_name'])
    except exceptions.NoDataFoundError:
        clan_member_ids = ()
    try:
        clan = Clan(
            clan_name = clan_name,
            leader_id = record['leader_id'],
            member_ids = clan_member_ids,
            reminder_channel_id = record['reminder_channel_id'],
            reminder_enabled = bool(record['reminder_enabled']),
            reminder_message = record['reminder_message'],
            reminder_role_id = record['reminder_role_id'],
        )
    except Exception as error:
        await errors.log_error(
            strings.INTERNAL_ERROR_DICT_TO_OBJECT.format(function=function_name, record=record)
        )
        raise LookupError(error)

    return clan


# Read Data
async def get_clan_by_member_id(user_id: int) -> Clan:
    """Gets all settings for a clan from a user id. The provided user can be a member or the owner.

    Returns
    -------
    Clan object

    Raises
    ------
    sqlite3.Error if something happened within the database.
    exceptions.NoDataFoundError if no guild was found.
    LookupError if something goes wrong reading the dict.
    Also logs all errors to the database.
    """
    table = 'clan_members'
    function_name = 'get_clan_by_member_id'
    sql = (
        f'SELECT * FROM {table} WHERE user_id=?'
    )
    try:
        cur = settings.DATABASE.cursor()
        cur.execute(sql, (user_id,))
        record = cur.fetchone()
    except sqlite3.Error as error:
        await errors.log_error(
            strings.INTERNAL_ERROR_SQLITE3.format(error=error, table=table, function=function_name, sql=sql)
        )
        raise
    if not record:
        raise exceptions.NoDataFoundError(f'No clan data found in database for user "{user_id}".')
    clan = await get_clan_by_clan_name(dict(record)['clan_name'])
    return clan


async def get_clan_by_leader_id(leader_id: int) -> Clan:
    """Gets all settings for a clan from a leader id.

    Returns
    -------
    Clan object

    Raises
    ------
    sqlite3.Error if something happened within the database.
    exceptions.NoDataFoundError if no guild was found.
    LookupError if something goes wrong reading the dict.
    Also logs all errors to the database.
    """
    table = 'clans'
    function_name = 'get_clan_by_leader_id'
    sql = f'SELECT * FROM {table} WHERE leader_id=?'
    try:
        cur = settings.DATABASE.cursor()
        cur.execute(sql, (leader_id,))
        record = cur.fetchone()
    except sqlite3.Error as error:
        await errors.log_error(
            strings.INTERNAL_ERROR_SQLITE3.format(error=error, table=table, function=function_name, sql=sql)
        )
        raise
    if not record:
        raise exceptions.NoDataFoundError(f'No clan data found in database with the leader id "{leader_id}".')
    clan = await _dict_to_clan(dict(record))
    return clan


async def get_clan_by_clan_name(clan_name: str) -> Clan:
    """Gets all settings for a clan from a clan name.

    Returns
    -------
    Clan object

    Raises
    ------
    sqlite3.Error if something happened within the database.
    exceptions.NoDataFoundError if no guild was found.
    LookupError if something goes wrong reading the dict.
    Also logs all errors to the database.
    """
    table = 'clans'
    function_name = 'get_clan_by_clan_name'
    sql = f'SELECT * FROM {table} WHERE clan_name=?'
    try:
        cur = settings.DATABASE.cursor()
        cur.execute(sql, (clan_name,))
        record = cur.fetchone()
    except sqlite3.Error as error:
        await errors.log_error(
            strings.INTERNAL_ERROR_SQLITE3.format(error=error, table=table, function=function_name, sql=sql)
        )
        raise
    if not record:
        raise exceptions.NoDataFoundError(f'No clan data found in database with clan name "{clan_name}".')
    clan = await _dict_to_clan(dict(record))
    return clan


async def get_clan_member_ids(clan_name: str) -> Clan:
    """Gets all clan member ids for a clan from a clan name.

    Returns
    -------
    Tuple[int]

    Raises
    ------
    sqlite3.Error if something happened within the database.
    exceptions.NoDataFoundError if no clan members were found.
    LookupError if something goes wrong reading the dict.
    Also logs all errors to the database.
    """
    table = 'clan_members'
    function_name = 'get_clan_members'
    sql = (
        f'SELECT * FROM {table} WHERE clan_name=?'
    )
    try:
        cur = settings.DATABASE.cursor()
        cur.execute(sql, (clan_name,))
        records = cur.fetchall()
    except sqlite3.Error as error:
        await errors.log_error(
            strings.INTERNAL_ERROR_SQLITE3.format(error=error, table=table, function=function_name, sql=sql)
        )
        raise
    if not records:
        raise exceptions.NoDataFoundError(f'No clan members found in database for clan "{clan_name}".')
    clan_member_ids = []
    for record in records:
        clan_member_ids.append(dict(record)['user_id'])
    return tuple(clan_member_ids)


# Write Data
async def _delete_clan(clan_settings: Clan) -> None:
    """Deletes clan record. Use Clan.delete() to trigger this function.

    Raises
    ------
    sqlite3.Error if something happened within the database.
    Also logs all errors to the database.
    """
    table = 'clans'
    function_name = '_delete_clan'
    sql = f'DELETE FROM {table} WHERE clan_name=?'
    try:
        cur = settings.DATABASE.cursor()
        cur.execute(sql, (clan_settings.clan_name,))
        table = 'clan_members'
        sql = f'DELETE FROM {table} WHERE clan_name=?'
        cur.execute(sql, (clan_settings.clan_name,))
    except sqlite3.Error as error:
        await errors.log_error(
            strings.INTERNAL_ERROR_SQLITE3.format(error=error, table=table, function=function_name, sql=sql)
        )
        raise

    
async def delete_clan_member(user_id: int) -> None:
    """Deletes a clan member record.

    Raises
    ------
    sqlite3.Error if something happened within the database.
    Also logs all errors to the database.
    """
    table = 'clan_members'
    function_name = 'delete_clan_member'
    sql = f'DELETE FROM {table} WHERE user_id=?'
    try:
        cur = settings.DATABASE.cursor()
        cur.execute(sql, (user_id,))
    except sqlite3.Error as error:
        await errors.log_error(
            strings.INTERNAL_ERROR_SQLITE3.format(error=error, table=table, function=function_name, sql=sql)
        )
        raise


async def _update_clan(clan_settings: Clan, **kwargs) -> None:
    """Updates clan record. Use Clan.update() to trigger this function.

    Arguments
    ---------
    clan_name: str
    kwargs (column=value):
        clan_name: str
        leader_id: int
        member_ids: Union[Tuple[int],List[int]] (up to 50)
        reminder_channel_id: int
        reminder_enabled: bool
        reminder_message: str
        reminder_role_id: int

    Note: If member_ids is passed this function will assume that these are all the members the clan has. Any members 
    in the database that are not in member_ids will be delete accordingly.
    If member_ids is not passed, no members will be changed.

    Raises
    ------
    sqlite3.Error if something happened within the database.
    NoArgumentsError if no kwargs are passed (need to pass at least one)
    Also logs all errors to the database.
    """
    table = 'clans'
    function_name = '_update_clan'
    if not kwargs:
        await errors.log_error(
            strings.INTERNAL_ERROR_NO_ARGUMENTS.format(table=table, function=function_name)
        )
        raise exceptions.NoArgumentsError('You need to specify at least one keyword argument.')
    if 'member_ids' in kwargs: 
        try:
            clan_member_ids = await get_clan_member_ids(clan_settings.clan_name)
        except exceptions.NoDataFoundError:
            clan_member_ids = ()
        new_member_ids = list(kwargs['member_ids'].copy())
        for member_id in clan_member_ids:
            if member_id not in kwargs['member_ids']:
                await delete_clan_member(member_id)
            else:
                new_member_ids.remove(member_id)
        for member_id in new_member_ids:
            await insert_clan_member(clan_settings.clan_name, member_id)
        del kwargs['member_ids']
    try:
        cur = settings.DATABASE.cursor()
        sql = f'UPDATE {table} SET'
        for kwarg in kwargs:
            sql = f'{sql} {kwarg} = :{kwarg},'
        sql = sql.strip(",")
        kwargs['clan_name_old'] = clan_settings.clan_name
        sql = f'{sql} WHERE clan_name = :clan_name_old'
        cur.execute(sql, kwargs)
    except sqlite3.Error as error:
        await errors.log_error(
            strings.INTERNAL_ERROR_SQLITE3.format(error=error, table=table, function=function_name, sql=sql)
        )
        raise


async def insert_clan(clan_name: str, leader_id: int, member_ids: Union[Tuple[int],List[int]]) -> Clan:
    """Inserts a record in the table "clans".

    Arguments
    ---------
    clan_name: str
    leader_id: int
    member_ids: Union[Tuple[int],List[int]] (up to 50)

    Returns
    -------
    Clan object with the newly created clan.

    Raises
    ------
    sqlite3.Error if something happened within the database.
    Also logs all errors to the database.
    """
    function_name = 'insert_clan'
    table = 'clans'
    
    sql = f'INSERT INTO {table} (clan_name, leader_id, reminder_message) VALUES (?, ?, ?)'
    try:
        cur = settings.DATABASE.cursor()
        cur.execute(sql, (clan_name, leader_id, strings.DEFAULT_MESSAGE_CLAN))
    except sqlite3.Error as error:
        await errors.log_error(
            strings.INTERNAL_ERROR_SQLITE3.format(error=error, table=table, function=function_name, sql=sql)
        )
        raise
    table = 'clan_members'
    try:
        sql = f'DELETE FROM {table} WHERE clan_name=?'
        cur.execute(sql, (clan_name,))
        for member_id in member_ids:
            sql = f'SELECT * FROM {table} WHERE user_id=?'
            cur.execute(sql, (member_id,))
            record = cur.fetchone()
            if record:
                sql = f'UPDATE {table} SET clan_name=? WHERE user_id=?'
                cur.execute(sql, (clan_name, member_id,))
            else:
                sql = f'INSERT INTO {table} (clan_name, user_id) VALUES (?,?)'
                cur.execute(sql, (clan_name, member_id,))
    except sqlite3.Error as error:
        await errors.log_error(
            strings.INTERNAL_ERROR_SQLITE3.format(error=error, table=table, function=function_name, sql=sql)
        )
        raise
    clan = await get_clan_by_clan_name(clan_name)
    return clan


async def insert_clan_member(clan_name: str, user_id: int) -> None:
    """Inserts a record in the table "clan_members".

    Raises
    ------
    sqlite3.Error if something happened within the database.
    Also logs all errors to the database.
    """
    function_name = 'insert_clan_member'
    table = 'clan_members'
    sql = f'INSERT INTO {table} (clan_name, user_id) VALUES (?, ?)'
    try:
        cur = settings.DATABASE.cursor()
        cur.execute(sql, (clan_name, user_id))
    except sqlite3.Error as error:
        await errors.log_error(
            strings.INTERNAL_ERROR_SQLITE3.format(error=error, table=table, function=function_name, sql=sql)
        )
        raise