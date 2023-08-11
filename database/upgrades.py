# upgrades.py
"""Provides access to the table "user_upgrades" in the database"""

from dataclasses import dataclass
import sqlite3
from typing import Tuple

from database import errors
from resources import exceptions, settings, strings


# Containers
@dataclass()
class Upgrade():
    """Object that represents a record from the table "user_upgrades"."""
    level: int
    name: str
    sort_index: int
    user_id: int

    async def refresh(self) -> None:
        """Refreshes clan data from the database.
        If the record doesn't exist anymore, "record_exists" will be set to False.
        All other values will stay on their old values before deletion (!).
        """
        try:
            new_settings = await get_upgrade(self.user_id, self.name)
        except exceptions.NoDataFoundError as error:
            return
        self.level = new_settings.level
        self.name = new_settings.name
        self.sort_index = new_settings.sort_index
        self.user_id = new_settings.user_id

    async def update(self, **kwargs) -> None:
        """Updates the record in the database. Also calls refresh().

        Arguments
        ---------
        kwargs (column=value):
            level: int
            name: str
            sort_index: int
            user_id: int
        """
        await _update_upgrade(self, **kwargs)
        await self.refresh()


# Miscellaneous functions
async def _dict_to_upgrade(record: dict) -> Upgrade:
    """Creates an Upgrade object from a database record

    Arguments
    ---------
    record: Database record from table "upgrade" as a dict.

    Returns
    -------
    Upgrade object.

    Raises
    ------
    LookupError if something goes wrong reading the dict. Also logs this error to the database.
    """
    function_name = '_dict_to_upgrade'
    try:
        reminder = Upgrade(
            level = record['level'],
            name = record['name'],
            sort_index = record['sort_index'],
            user_id = record['user_id'],
        )
    except Exception as error:
        await errors.log_error(
            strings.INTERNAL_ERROR_DICT_TO_OBJECT.format(function=function_name, record=record)
        )
        raise LookupError(error)

    return reminder


# Read Data
async def get_upgrade(user_id: int, name: str) -> Upgrade:
    """Gets an upgrade for a user id and an upgrade name.

    Arguments
    ---------
    user_id: int
    name: str

    Returns
    -------
    Upgrade object

    Raises
    ------
    sqlite3.Error if something happened within the database.
    exceptions.NoDataFoundError if no upgrade was found.
    LookupError if something goes wrong reading the dict.
    Also logs all errors to the database.
    """
    table = 'user_upgrades'
    function_name = 'get_upgrade'
    sql = f'SELECT * FROM {table} WHERE user_id=? AND name=?'
    try:
        cur = settings.DATABASE.cursor()
        cur.execute(sql, (user_id, name))
        record = cur.fetchone()
    except sqlite3.Error as error:
        await errors.log_error(
            strings.INTERNAL_ERROR_SQLITE3.format(error=error, table=table, function=function_name, sql=sql)
        )
        raise
    if not record:
        raise exceptions.NoDataFoundError(
            f'No upgrade data found in database for user "{user_id}" and name "{name}".'
        )
    upgrade = await _dict_to_upgrade(dict(record))
    return upgrade


async def get_all_upgrades(user_id: int) -> Tuple[Upgrade]:
    """Gets all upgrades of a user.

    Arguments
    ---------
    user_id: int

    Returns
    -------
    Tuple[Upgrade]

    Raises
    ------
    sqlite3.Error if something happened within the database.
    exceptions.NoDataFoundError if no upgrade was found.
    LookupError if something goes wrong reading the dict.
    Also logs all errors to the database.
    """
    table = 'user_upgrades'
    function_name = 'get_active_upgrades'
    sql = f'SELECT * FROM {table} WHERE user_id=? ORDER BY sort_index ASC'
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
        error_message = f'No upgrades found for user {user_id} in database.'
        raise exceptions.NoDataFoundError(error_message)
    upgrades = []
    for record in records:
        upgrade = await _dict_to_upgrade(dict(record))
        upgrades.append(upgrade)
    return tuple(upgrades)


# Write Data
async def _update_upgrade(upgrade: Upgrade, **kwargs) -> None:
    """Updates upgrade record. Use Upgrade.update() to trigger this function.

    Arguments
    ---------
    upgrade: Upgrade
    kwargs (column=value):
        level: int
        name: str
        sort_index: int
        user_id: int

    Raises
    ------
    sqlite3.Error if something happened within the database.
    NoArgumentsError if no kwargs are passed (need to pass at least one)
    Also logs all errors to the database.
    """
    table = 'user_upgrades'
    function_name = '_update_upgrade'
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
        kwargs['user_id'] = upgrade.user_id
        kwargs['name'] = upgrade.name
        sql = f'{sql} WHERE user_id=:user_id AND name=:name'
        cur.execute(sql, kwargs)
    except sqlite3.Error as error:
        await errors.log_error(
            strings.INTERNAL_ERROR_SQLITE3.format(error=error, table=table, function=function_name, sql=sql)
        )
        raise


async def insert_upgrade(user_id: int, name: str, level: int, sort_index: int) -> Upgrade:
    """Inserts an upgrade record.

    Arguments
    ---------
    user_id: int
    name: str
    level: int
    sort_index: int

    Returns
    -------
    Upgrade object with the newly created upgrade.

    Raises
    ------
    sqlite3.Error if something happened within the database.
    Also logs all errors to the database.
    """
    function_name = 'insert_upgrade'
    table = 'user_upgrades'
    try:
        cur = settings.DATABASE.cursor()
    except sqlite3.Error as error:
        await errors.log_error(
            strings.INTERNAL_ERROR_SQLITE3.format(error=error, table=table, function=function_name, sql=sql)
        )
        raise
    sql = (
        f'INSERT INTO {table} (user_id, level, name, sort_index) '
        f'VALUES (?, ?, ?, ?)'
    )
    try:
        cur.execute(sql, (user_id, level, name, sort_index))
    except sqlite3.Error as error:
        await errors.log_error(
            strings.INTERNAL_ERROR_SQLITE3.format(error=error, table=table, function=function_name, sql=sql)
        )
        raise
    upgrade = await get_upgrade(user_id, name)

    return upgrade