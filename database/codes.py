# codes.py
"""Provides access to the table "codes" in the database"""

import sqlite3
from typing import NamedTuple, Tuple

from database import errors
from resources import exceptions, settings, strings


# Containers
class Code(NamedTuple):
    """Object that contains a code and its contents"""
    code: str
    contents: str


# Miscellaneous functions
async def _dict_to_code(record: dict) -> Code:
    """Creates a Code object from a database record

    Arguments
    ---------
    record: Database record from table "codes" as a dict.

    Returns
    -------
    Code object.

    Raises
    ------
    LookupError if something goes wrong reading the dict. Also logs this error to the database.
    """
    function_name = '_dict_to_code'
    try:
        code = Code(
            code = record['code'],
            contents = record['contents'],
        )
    except Exception as error:
        await errors.log_error(
            strings.INTERNAL_ERROR_DICT_TO_OBJECT.format(function=function_name, record=record)
        )
        raise LookupError(error)

    return code


# Get data
async def get_all_codes() -> Tuple[Code]:
    """Gets all codes.

    Returns
    -------
    Tuple with Code objects

    Raises
    ------
    sqlite3.Error if something happened within the database.
    exceptions.NoDataFoundError if no guild was found.
    LookupError if something goes wrong reading the dict.
    Also logs all errors to the database.
    """
    table = 'codes'
    function_name = 'get_all_codes'
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
        raise exceptions.FirstTimeUserError(f'No codes found in database.')
    codes = []
    for record in records:
        code = await _dict_to_code(dict(record))
        codes.append(code)

    return tuple(codes)