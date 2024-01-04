# clans.py
"""Provides access to the tables "clans" and "clan_members" in the database"""

from argparse import ArgumentError
import copy
from dataclasses import dataclass
import sqlite3
from typing import Dict, NamedTuple, Optional, Tuple

from database import errors
from resources import exceptions, settings, strings


# Containers
class ClanMember(NamedTuple):
    """Object that summarizes all member settings for a clan member"""
    user_id: int
    guild_seals_contributed: int


@dataclass()
class Clan():
    """Object that represents a record from table "clans"."""
    alert_contribution_enabled: bool
    alert_contribution_message: str
    clan_name: str
    helper_teamraid_enabled: bool
    leader_id: int
    members: Tuple[ClanMember]
    reminder_channel_id: int
    reminder_enabled: bool
    reminder_message: str
    reminder_offset: float
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
        self.alert_contribution_enabled = new_settings.alert_contribution_enabled
        self.alert_contribution_message = new_settings.alert_contribution_message
        self.helper_teamraid_enabled = new_settings.helper_teamraid_enabled
        self.leader_id = new_settings.leader_id
        self.members = new_settings.members
        self.reminder_channel_id = new_settings.reminder_channel_id
        self.reminder_enabled = new_settings.reminder_enabled
        self.reminder_message = new_settings.reminder_message
        self.reminder_offset = new_settings.reminder_offset
        self.reminder_role_id = new_settings.reminder_role_id

    async def update(self, **kwargs) -> None:
        """Updates the clan record in the database. Also calls refresh().

        Arguments
        ---------
        kwargs (column=value):
            alert_contribution_enabled: bool
            alert_contribution_message: str
            clan_name: str
            helper_teamraid_enabled: bool
            leader_id: int
            members: Dict[user_id: guild_seals_contributed] (up to 50)
            reminder_channel_id: int
            reminder_enabled: bool
            reminder_message: str
            reminder_offset: float
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
        clan_members = await get_clan_members(record['clan_name'])
    except exceptions.NoDataFoundError:
        clan_members = ()
    try:
        clan = Clan(
            alert_contribution_enabled = bool(record['alert_contribution_enabled']),
            alert_contribution_message = record['alert_contribution_message'],
            clan_name = clan_name,
            helper_teamraid_enabled = bool(record['helper_teamraid_enabled']),
            leader_id = record['leader_id'],
            members = clan_members,
            reminder_channel_id = record['reminder_channel_id'],
            reminder_enabled = bool(record['reminder_enabled']),
            reminder_message = record['reminder_message'],
            reminder_offset = record['reminder_offset'],
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


async def get_all_clans() -> Tuple[Clan]:
    """Gets all settings for a clan from a clan name.

    Returns
    -------
    Tuple with Clan objects

    Raises
    ------
    sqlite3.Error if something happened within the database.
    exceptions.NoDataFoundError if no guild was found.
    LookupError if something goes wrong reading the dict.
    Also logs all errors to the database.
    """
    table = 'clans'
    function_name = 'get_all_clans'
    sql = f'SELECT * FROM {table}'
    try:
        cur = settings.DATABASE.cursor()
        cur.execute(sql)
        records = cur.fetchall()
    except sqlite3.Error as error:
        await errors.log_error(
            strings.INTERNAL_ERROR_SQLITE3.format(error=error, table=table, function=function_name, sql=sql)
        )
        raise
    if not records:
        raise exceptions.NoDataFoundError(f'No clan data found in database.')
    clans = []
    for record in records:
        clan = await _dict_to_clan(dict(record))
        clans.append(clan)
    return tuple(clans)


async def get_clan_members(clan_name: str) -> Tuple[ClanMember]:
    """Gets all clan members for a clan from a clan name.

    Returns
    -------
    Tuple[ClanMember]

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
    clan_members = []
    for record in records:
        record = dict(record)
        clan_member = ClanMember(
            user_id = record['user_id'],
            guild_seals_contributed = record['guild_seals_contributed'],
        )
        clan_members.append(clan_member)
    return tuple(clan_members)


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
        alert_contribution_enabled: bool
        alert_contribution_message: str
        clan_name: str
        helper_teamraid_enabled: bool
        leader_id: int
        members: Dict[user_id: guild_seals_contributed] (up to 50)
        reminder_channel_id: int
        reminder_enabled: bool
        reminder_message: str
        reminder_offset: float
        reminder_role_id: int

    Note: If members is passed, this function will assume that these are all the members the clan has. Any members 
    in the database that are not in members will be delete accordingly.
    If members is not passed, no members will be changed.

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
    if 'members' in kwargs: 
        try:
            clan_members = await get_clan_members(clan_settings.clan_name)
        except exceptions.NoDataFoundError:
            clan_members = ()
        new_members = copy.deepcopy(kwargs['members'])
        for clan_member in clan_members:
            if clan_member.user_id not in kwargs['members']:
                await delete_clan_member(clan_member.user_id)
            else:
                await update_clan_member(clan_member.user_id, guild_seals_contributed=new_members[clan_member.user_id])
                del new_members[clan_member.user_id]
        for member_id, guild_seals_contributed in new_members.items():
            try:
                await delete_clan_member(member_id)
            except sqlite3.Error:
                pass
            await insert_clan_member(clan_settings.clan_name, member_id, guild_seals_contributed)
        del kwargs['members']
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


async def insert_clan(clan_name: str, leader_id: int, members: Dict[int, int]) -> Clan:
    """Inserts a record in the table "clans".

    Arguments
    ---------
    clan_name: str
    leader_id: int
    members: Dict[user_id: guild_seals_contributed] (up to 50)

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
    
    sql = (
        f'INSERT INTO {table} (alert_contribution_enabled, alert_contribution_message, clan_name, leader_id, '
        f'reminder_message, helper_teamraid_enabled) VALUES (?, ?, ?, ?, ?, ?)')
    try:
        cur = settings.DATABASE.cursor()
        cur.execute(sql, (0, strings.DEFAULT_MESSAGE_CONTRIBUTION_ALERT, clan_name, leader_id, strings.DEFAULT_MESSAGE_CLAN, 1))
    except sqlite3.Error as error:
        await errors.log_error(
            strings.INTERNAL_ERROR_SQLITE3.format(error=error, table=table, function=function_name, sql=sql)
        )
        raise
    table = 'clan_members'
    try:
        sql = f'DELETE FROM {table} WHERE clan_name=?'
        cur.execute(sql, (clan_name,))
        for member_id, guild_seals_contributed in members.items():
            sql = f'SELECT * FROM {table} WHERE user_id=?'
            cur.execute(sql, (member_id,))
            record = cur.fetchone()
            if record:
                sql = f'UPDATE {table} SET clan_name=?, guild_seals_contributed=? WHERE user_id=?'
                cur.execute(sql, (clan_name, guild_seals_contributed, member_id))
            else:
                sql = f'INSERT INTO {table} (clan_name, user_id, guild_seals_contributed) VALUES (?,?,?)'
                cur.execute(sql, (clan_name, member_id, guild_seals_contributed))
    except sqlite3.Error as error:
        await errors.log_error(
            strings.INTERNAL_ERROR_SQLITE3.format(error=error, table=table, function=function_name, sql=sql)
        )
        raise
    clan = await get_clan_by_clan_name(clan_name)
    return clan


async def insert_clan_member(clan_name: str, user_id: int, guild_seals_contributed: Optional[int] = 0) -> None:
    """Inserts a record in the table "clan_members".

    Raises
    ------
    sqlite3.Error if something happened within the database.
    Also logs all errors to the database.
    """
    function_name = 'insert_clan_member'
    table = 'clan_members'
    sql = f'INSERT INTO {table} (clan_name, user_id, guild_seals_contributed) VALUES (?, ?, ?)'
    try:
        cur = settings.DATABASE.cursor()
        cur.execute(sql, (clan_name, user_id, guild_seals_contributed))
    except sqlite3.Error as error:
        await errors.log_error(
            strings.INTERNAL_ERROR_SQLITE3.format(error=error, table=table, function=function_name, sql=sql)
        )
        raise


async def update_clan_member(user_id: int, clan_name: Optional[str] = None,
                             guild_seals_contributed: Optional[int] = None) -> None:
    """Updates a clan member record.

    Arguments
    ---------
    user_id: int
    clan_name: str
    guild_seals_contributed: int

    Raises
    ------
    sqlite3.Error if something happened within the database.
    ArgumentError if value is None
    Also logs all errors to the database.
    """
    table = 'clan_members'
    function_name = 'update_clan_member'
    if clan_name is None and guild_seals_contributed is None:
        raise ArgumentError('Arguments can\'t all be None.')
    cur = settings.DATABASE.cursor()
    try:
        sql = f'SELECT * FROM {table} WHERE user_id = ?'
        cur.execute(sql, (user_id,))
        record = cur.fetchone()
        clan_member = dict(record)
        if clan_name is None: clan_name = clan_member['clan_name']
        if guild_seals_contributed is None: guild_seals_contributed = clan_member['guild_seals_contributed']
        sql = f'UPDATE {table} SET clan_name = ?, guild_seals_contributed = ? WHERE user_id = ?'
        cur.execute(sql, (clan_name, guild_seals_contributed, user_id))
    except sqlite3.Error as error:
        await errors.log_error(
            strings.INTERNAL_ERROR_SQLITE3.format(error=error, table=table, function=function_name, sql=sql)
        )
        raise