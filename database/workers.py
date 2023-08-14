# upgrades.py
"""Provides access to the tables "user_workers" and "worker_levels" in the database"""

from argparse import ArgumentError
from dataclasses import dataclass
import sqlite3
from typing import Optional, Tuple

from database import errors
from resources import exceptions, settings, strings


# Containers
@dataclass()
class UserWorker():
    """Object that represents a record from the table "user_workers"."""
    user_id: int
    worker_amount: int
    worker_level: int
    worker_name: str

    async def refresh(self) -> None:
        """Refreshes data from the database."""
        try:
            new_settings = await get_user_worker(self.user_id, self.worker_name)
        except exceptions.NoDataFoundError as error:
            return
        self.user_id = new_settings.user_id
        self.worker_amount = new_settings.worker_amount
        self.worker_level = new_settings.worker_level
        self.worker_name = new_settings.worker_name

    async def update(self, **kwargs) -> None:
        """Updates the record in the database. Also calls refresh().

        Arguments
        ---------
        kwargs (column=value):
            user_id: int
            worker_amount: int
            worker_level: int
            worker_name: str
        """
        await _update_user_worker(self, **kwargs)
        await self.refresh()


@dataclass()
class WorkerLevel():
    """Object that represents a record from the table "worker_levels"."""
    level: int
    workers_required: int

    async def refresh(self) -> None:
        """Refreshes data from the database."""
        try:
            new_settings = await get_worker_level(self.level)
        except exceptions.NoDataFoundError as error:
            return
        self.level = new_settings.level
        self.workers_required = new_settings.workers_required

    async def update(self, **kwargs) -> None:
        """Updates the record in the database. Also calls refresh().

        Arguments
        ---------
        kwargs (column=value):
            level: int
            workers_required: int
        """
        await _update_worker_level(self, **kwargs)
        await self.refresh()



# Miscellaneous functions
async def _dict_to_user_worker(record: dict) -> UserWorker:
    """Creates an UserWorker object from a database record

    Arguments
    ---------
    record: Database record from table "user_workers" as a dict.

    Returns
    -------
    UserWorker object.

    Raises
    ------
    LookupError if something goes wrong reading the dict. Also logs this error to the database.
    """
    function_name = '_dict_to_user_workers'
    try:
        user_worker = UserWorker(
            user_id = record['user_id'],
            worker_amount = record['worker_amount'],
            worker_level = record['worker_level'],
            worker_name = record['worker_name'],
        )
    except Exception as error:
        await errors.log_error(
            strings.INTERNAL_ERROR_DICT_TO_OBJECT.format(function=function_name, record=record)
        )
        raise LookupError(error)

    return user_worker


async def _dict_to_worker_level(record: dict) -> WorkerLevel:
    """Creates an WorkerLevel object from a database record

    Arguments
    ---------
    record: Database record from table "worker_levels" as a dict.

    Returns
    -------
    WorkerLevel object.

    Raises
    ------
    LookupError if something goes wrong reading the dict. Also logs this error to the database.
    """
    function_name = '_dict_to_worker_level'
    try:
        worker_level = WorkerLevel(
            level = record['level'],
            workers_required = record['workers_required'],
        )
    except Exception as error:
        await errors.log_error(
            strings.INTERNAL_ERROR_DICT_TO_OBJECT.format(function=function_name, record=record)
        )
        raise LookupError(error)

    return worker_level



# Read Data
async def get_user_worker(user_id: int, worker_name: str) -> UserWorker:
    """Gets an upgrade for a user id and an upgrade name.

    Arguments
    ---------
    user_id: int
    worker_name: str

    Returns
    -------
    UserWorker object

    Raises
    ------
    sqlite3.Error if something happened within the database.
    exceptions.NoDataFoundError if no upgrade was found.
    LookupError if something goes wrong reading the dict.
    Also logs all errors to the database.
    """
    table = 'user_workers'
    function_name = 'get_user_worker'
    sql = f'SELECT * FROM {table} WHERE user_id=? AND worker_name=?'
    try:
        cur = settings.DATABASE.cursor()
        cur.execute(sql, (user_id, worker_name))
        record = cur.fetchone()
    except sqlite3.Error as error:
        await errors.log_error(
            strings.INTERNAL_ERROR_SQLITE3.format(error=error, table=table, function=function_name, sql=sql)
        )
        raise
    if not record:
        raise exceptions.NoDataFoundError(
            f'No worker data found in database for user "{user_id}" and worker name "{worker_name}".'
        )
    user_worker = await _dict_to_user_worker(dict(record))
    return user_worker


async def get_user_workers(user_id: int) -> Tuple[UserWorker]:
    """Gets all workers of a user.

    Arguments
    ---------
    user_id: int

    Returns
    -------
    Tuple[UserWorker]

    Raises
    ------
    sqlite3.Error if something happened within the database.
    exceptions.NoDataFoundError if no upgrade was found.
    LookupError if something goes wrong reading the dict.
    Also logs all errors to the database.
    """
    table = 'user_workers'
    function_name = 'get_user_workers'
    sql = f'SELECT * FROM {table} WHERE user_id=?'
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
        error_message = f'No workers found for user {user_id} in database.'
        raise exceptions.NoDataFoundError(error_message)
    user_workers = []
    for record in records:
        user_worker = await _dict_to_user_worker(dict(record))
        user_workers.append(user_worker)
    return tuple(user_workers)


async def get_worker_level(level: Optional[int] = None, workers_required: Optional[int] = None) -> WorkerLevel:
    """Gets worker level data for a worker level.

    Arguments
    ---------
    level: int
    OR
    workers_required: int

    Returns
    -------
    WorkerLevel object

    Raises
    ------
    sqlite3.Error if something happened within the database.
    exceptions.NoDataFoundError if no upgrade was found.
    LookupError if something goes wrong reading the dict.
    Also logs all errors to the database.
    ArgumentError if level and workers_requried are both None or both set.
    """
    if level is None and workers_required is None:
        raise ArgumentError('One of these arguments has to be defined: level, workers_required.')
    if level is not None and workers_required is not None:
        raise ArgumentError('Only one of these arguments can be defined: level, workers_required.')
    condition = 'level' if level is not None else 'workers_required'
    condition_value = level if level is not None else workers_required
    table = 'worker_levels'
    function_name = 'get_worker_level'
    sql = f'SELECT * FROM {table} WHERE {condition}=?'
    try:
        cur = settings.DATABASE.cursor()
        cur.execute(sql, (condition_value,))
        record = cur.fetchone()
    except sqlite3.Error as error:
        await errors.log_error(
            strings.INTERNAL_ERROR_SQLITE3.format(error=error, table=table, function=function_name, sql=sql)
        )
        raise
    if not record:
        raise exceptions.NoDataFoundError(
            f'No data found in database for the worker level "{level}" and the workers required "{workers_required}".'
        )
    worker_level = await _dict_to_worker_level(dict(record))
    return worker_level


async def get_worker_levels() -> Tuple[WorkerLevel]:
    """Gets all worker levels

    Returns
    -------
    Tuple[WorkerLevel]

    Raises
    ------
    sqlite3.Error if something happened within the database.
    exceptions.NoDataFoundError if no upgrade was found.
    LookupError if something goes wrong reading the dict.
    Also logs all errors to the database.
    """
    table = 'worker_levels'
    function_name = 'get_worker_levels'
    sql = f'SELECT * FROM {table} ORDER BY level ASC'
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
        error_message = f'No worker levels found in database.'
        raise exceptions.NoDataFoundError(error_message)
    worker_levels = []
    for record in records:
        worker_level = await _dict_to_worker_level(dict(record))
        worker_levels.append(worker_level)
    return tuple(worker_levels)


# Write Data
async def _update_user_worker(user_worker: UserWorker, **kwargs) -> None:
    """Updates a user worker record. Use UserWorker.update() to trigger this function.

    Arguments
    ---------
    user_worker: UserWorker
    kwargs (column=value):
        user_id: int
        worker_amount: int
        worker_level: int
        worker_name: str

    Raises
    ------
    sqlite3.Error if something happened within the database.
    NoArgumentsError if no kwargs are passed (need to pass at least one)
    Also logs all errors to the database.
    """
    table = 'user_workers'
    function_name = '_update_user_worker'
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
        kwargs['user_id'] = user_worker.user_id
        kwargs['worker_name'] = user_worker.worker_name
        sql = f'{sql} WHERE user_id=:user_id AND worker_name=:worker_name'
        cur.execute(sql, kwargs)
    except sqlite3.Error as error:
        await errors.log_error(
            strings.INTERNAL_ERROR_SQLITE3.format(error=error, table=table, function=function_name, sql=sql)
        )
        raise


async def _update_worker_level(worker_level: WorkerLevel, **kwargs) -> None:
    """Updates a worker level record. Use WorkerLevel.update() to trigger this function.

    Arguments
    ---------
    worker_level: WorkerLevel
    kwargs (column=value):
        level: int
        workers_required: int        

    Raises
    ------
    sqlite3.Error if something happened within the database.
    NoArgumentsError if no kwargs are passed (need to pass at least one)
    Also logs all errors to the database.
    """
    table = 'worker_levels'
    function_name = '_update_worker_level'
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
        kwargs['level'] = worker_level.level
        sql = f'{sql} WHERE level=:level'
        cur.execute(sql, kwargs)
    except sqlite3.Error as error:
        await errors.log_error(
            strings.INTERNAL_ERROR_SQLITE3.format(error=error, table=table, function=function_name, sql=sql)
        )
        raise


async def insert_user_worker(user_id: int, worker_name: str, worker_level: int, worker_amount: int) -> UserWorker:
    """Inserts an user worker record.

    Arguments
    ---------
    user_id: int
    worker_amount: int
    worker_level: int
    worker_name: str

    Returns
    -------
    UserWorker object with the newly created upgrade.

    Raises
    ------
    sqlite3.Error if something happened within the database.
    Also logs all errors to the database.
    """
    function_name = 'insert_user_worker'
    table = 'user_workers'
    try:
        cur = settings.DATABASE.cursor()
    except sqlite3.Error as error:
        await errors.log_error(
            strings.INTERNAL_ERROR_SQLITE3.format(error=error, table=table, function=function_name, sql=sql)
        )
        raise
    sql = (
        f'INSERT INTO {table} (user_id, worker_name, worker_level, worker_amount) '
        f'VALUES (?, ?, ?, ?)'
    )
    try:
        cur.execute(sql, (user_id, worker_name, worker_level, worker_amount))
    except sqlite3.Error as error:
        await errors.log_error(
            strings.INTERNAL_ERROR_SQLITE3.format(error=error, table=table, function=function_name, sql=sql)
        )
        raise
    user_worker = await get_user_worker(user_id, worker_name)

    return user_worker


async def insert_worker_level(level: int, workers_required: int) -> WorkerLevel:
    """Inserts an worker level record.

    Arguments
    ---------
    level: int
    workers_required: int

    Returns
    -------
    WorkerLevel object with the newly created upgrade.

    Raises
    ------
    sqlite3.Error if something happened within the database.
    Also logs all errors to the database.
    """
    function_name = 'insert_worker_level'
    table = 'worker_levels'
    try:
        cur = settings.DATABASE.cursor()
    except sqlite3.Error as error:
        await errors.log_error(
            strings.INTERNAL_ERROR_SQLITE3.format(error=error, table=table, function=function_name, sql=sql)
        )
        raise
    sql = (
        f'INSERT INTO {table} (level, workers_required) '
        f'VALUES (?, ?)'
    )
    try:
        cur.execute(sql, (level, workers_required))
    except sqlite3.Error as error:
        await errors.log_error(
            strings.INTERNAL_ERROR_SQLITE3.format(error=error, table=table, function=function_name, sql=sql)
        )
        raise
    worker_level = await get_worker_level(level, workers_required)

    return worker_level