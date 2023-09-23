# users.py
"""Provides access to the table "users" in the database"""

from dataclasses import dataclass
from datetime import datetime
import sqlite3
from typing import NamedTuple, Tuple

from database import errors
from resources import exceptions, settings, strings


# Containers
class UserReminder(NamedTuple):
    """Object that summarizes all user settings for a specific alert"""
    enabled: bool
    message: str

@dataclass()
class User():
    """Object that represents a record from table "user"."""
    bot_enabled: bool
    dnd_mode_enabled: bool
    energy_full_time: datetime
    energy_max: int
    donor_tier: int
    helper_context_enabled: bool
    helper_profile_enabled: bool
    helper_profile_ready_commands_visible: bool
    helper_raid_enabled: bool
    helper_raid_compact_mode_enabled: bool
    helper_raid_names_enabled: bool
    helper_upgrades_enabled: bool
    idlucks: int
    last_claim_time: datetime
    reactions_enabled: bool
    reminder_channel_id: int
    reminder_claim: UserReminder
    reminder_claim_last_selection: float
    reminder_custom: UserReminder
    reminder_daily: UserReminder
    reminder_energy: UserReminder
    reminder_energy_last_selection: int
    reminder_shop: UserReminder
    reminder_vote: UserReminder
    reminders_as_embed: bool
    reminders_daily_offset: float
    reminders_slash_enabled: bool
    tracking_enabled: bool
    time_compressors_used: int
    time_speeders_used: int
    user_id: int

    async def refresh(self) -> None:
        """Refreshes user data from the database."""
        new_settings: User = await get_user(self.user_id)
        self.bot_enabled = new_settings.bot_enabled
        self.dnd_mode_enabled = new_settings.dnd_mode_enabled
        self.donor_tier = new_settings.donor_tier
        self.energy_full_time = new_settings.energy_full_time
        self.energy_max = new_settings.energy_max
        self.helper_context_enabled = new_settings.helper_context_enabled
        self.helper_profile_enabled = new_settings.helper_profile_enabled
        self.helper_profile_ready_commands_visible = new_settings.helper_profile_ready_commands_visible
        self.helper_raid_enabled = new_settings.helper_raid_enabled
        self.helper_raid_compact_mode_enabled = new_settings.helper_raid_compact_mode_enabled
        self.helper_raid_names_enabled = new_settings.helper_raid_names_enabled
        self.helper_upgrades_enabled = new_settings.helper_upgrades_enabled
        self.idlucks = new_settings.idlucks
        self.last_claim_time = new_settings.last_claim_time
        self.reactions_enabled = new_settings.reactions_enabled
        self.reminder_channel_id = new_settings.reminder_channel_id
        self.reminder_claim = new_settings.reminder_claim
        self.reminder_claim_last_selection = new_settings.reminder_claim_last_selection
        self.reminder_custom = new_settings.reminder_custom
        self.reminder_daily = new_settings.reminder_daily
        self.reminder_energy = new_settings.reminder_energy
        self.reminder_energy_last_selection = new_settings.reminder_energy_last_selection
        self.reminder_shop = new_settings.reminder_shop
        self.reminder_vote = new_settings.reminder_vote
        self.reminders_as_embed = new_settings.reminders_as_embed
        self.reminders_daily_offset = new_settings.reminders_daily_offset
        self.reminders_slash_enabled = new_settings.reminders_slash_enabled
        self.time_compressors_used = new_settings.time_compressors_used
        self.time_speeders_used = new_settings.time_speeders_used
        self.tracking_enabled = new_settings.tracking_enabled

    async def update(self, **kwargs) -> None:
        """Updates the user record in the database. Also calls refresh().
        If user_donor_tier is updated and a partner is set, the partner's partner_donor_tier is updated as well.

        Arguments
        ---------
        kwargs (column=value):
            bot_enabled: bool
            dnd_mode_enabled: bool
            donor_tier: int
            energy_full_time: datetime UTC aware
            energy_max: int
            helper_context_enabled: bool
            helper_profile_enabled: bool
            helper_profile_ready_commands_visible: bool
            helper_raid_enabled: bool
            helper_raid_compact_mode_enabled: bool
            helper_raid_names_enabled: bool
            helper_upgrades_enabled: bool
            idlucks: int
            last_claim_time: datetime UTC aware
            reactions_enabled: bool
            reminder_channel_id: Optional[int] = None
            reminder_claim_enabled: bool
            reminder_claim_message: str
            reminder_claim_last_selection: float
            reminder_custom_message: str
            reminder_daily_enabled: bool
            reminder_daily_message: str
            reminder_energy_enabled: bool
            reminder_energy_last_selection: int
            reminder_energy_message: str
            reminder_shop_enabled: bool
            reminder_shop_message: str
            reminder_vote_enabled: bool
            reminder_vote_message: str
            reminders_as_embed: bool
            reminders_daily_offset: float
            reminders_slash_enabled: bool
            time_compressors_used: int
            time_speeders_used: int
            tracking_enabled: bool
        """
        await _update_user(self, **kwargs)
        await self.refresh()


# Miscellaneous functions
async def _dict_to_user(record: dict) -> User:
    """Creates a User object from a database record

    Arguments
    ---------
    record: Database record from table "user" as a dict.

    Returns
    -------
    User object.

    Raises
    ------
    LookupError if something goes wrong reading the dict. Also logs this error to the database.
    """
    function_name = '_dict_to_user'
    energy_full_time = last_claim_time = None
    if record['energy_full_time'] is not None:
        energy_full_time = datetime.fromisoformat(record['energy_full_time'])
    if record['last_claim_time'] is not None:
        last_claim_time = datetime.fromisoformat(record['last_claim_time'])
    try:
        user = User(
            bot_enabled = bool(record['bot_enabled']),
            dnd_mode_enabled = bool(record['dnd_mode_enabled']),
            donor_tier = record['donor_tier'],
            energy_full_time = energy_full_time,
            energy_max = record['energy_max'],
            helper_context_enabled = bool(record['helper_context_enabled']),
            helper_profile_enabled = bool(record['helper_profile_enabled']),
            helper_profile_ready_commands_visible = bool(record['helper_profile_ready_commands_visible']),
            helper_raid_enabled = bool(record['helper_raid_enabled']),
            helper_raid_compact_mode_enabled = bool(record['helper_raid_compact_mode_enabled']),
            helper_raid_names_enabled = bool(record['helper_raid_names_enabled']),
            helper_upgrades_enabled = bool(record['helper_upgrades_enabled']),
            idlucks = record['idlucks'],
            last_claim_time = last_claim_time,
            reactions_enabled = bool(record['reactions_enabled']),
            reminder_channel_id = record['reminder_channel_id'],
            reminder_claim = UserReminder(enabled=bool(record['reminder_claim_enabled']),
                                          message=record['reminder_claim_message']),
            reminder_claim_last_selection = record['reminder_claim_last_selection'],
            reminder_custom = UserReminder(enabled=True,
                                           message=record['reminder_custom_message']),
            reminder_daily = UserReminder(enabled=bool(record['reminder_daily_enabled']),
                                          message=record['reminder_daily_message']),
            reminder_energy = UserReminder(enabled=bool(record['reminder_energy_enabled']),
                                          message=record['reminder_energy_message']),
            reminder_energy_last_selection = record['reminder_energy_last_selection'],
            reminder_shop = UserReminder(enabled=bool(record['reminder_shop_enabled']),
                                          message=record['reminder_shop_message']),
            reminder_vote = UserReminder(enabled=bool(record['reminder_vote_enabled']),
                                         message=record['reminder_vote_message']),
            reminders_as_embed = bool(record['reminders_as_embed']),
            reminders_daily_offset = record['reminders_daily_offset'],
            reminders_slash_enabled = bool(record['reminders_slash_enabled']),
            time_compressors_used = record['time_compressors_used'],
            time_speeders_used = record['time_speeders_used'],
            tracking_enabled = bool(record['tracking_enabled']),            
            user_id = record['user_id'],
        )
    except Exception as error:
        await errors.log_error(
            strings.INTERNAL_ERROR_DICT_TO_OBJECT.format(function=function_name, record=record)
        )
        raise LookupError(error)

    return user


# Get data
async def get_user(user_id: int) -> User:
    """Gets all user settings.

    Returns
    -------
    User object

    Raises
    ------
    sqlite3.Error if something happened within the database.
    exceptions.FirstTimeUserError if no user was found.
    LookupError if something goes wrong reading the dict.
    Also logs all errors to the database.
    """
    table = 'users'
    function_name = 'get_user'
    sql = f'SELECT * FROM {table} WHERE user_id=?'
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
        raise exceptions.FirstTimeUserError(f'No user data found in database for user "{user_id}".')
    user = await _dict_to_user(dict(record))

    return user


async def get_all_users() -> Tuple[User]:
    """Gets all user settings of all users.

    Returns
    -------
    Tuple with User objects

    Raises
    ------
    sqlite3.Error if something happened within the database.
    exceptions.NoDataFoundError if no guild was found.
    LookupError if something goes wrong reading the dict.
    Also logs all errors to the database.
    """
    table = 'users'
    function_name = 'get_all_users'
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
        raise exceptions.FirstTimeUserError(f'No user data found in database (how likely is that).')
    users = []
    for record in records:
        user = await _dict_to_user(dict(record))
        users.append(user)

    return tuple(users)


async def get_user_count() -> int:
    """Gets the amount of users in the table "users".

    Returns
    -------
    Amound of users: int

    Raises
    ------
    sqlite3.Error if something happened within the database. Also logs this error to the log file.
    """
    table = 'users'
    function_name = 'get_user_count'
    sql = f'SELECT COUNT(user_id) FROM {table}'
    try:
        cur = settings.DATABASE.cursor()
        cur.execute(sql)
        record = cur.fetchone()
    except sqlite3.Error as error:
        await errors.log_error(
            strings.INTERNAL_ERROR_SQLITE3.format(error=error, table=table, function=function_name, sql=sql)
        )
        raise
    (user_count,) = record

    return user_count


# Write Data
async def _update_user(user: User, **kwargs) -> None:
    """Updates user record. Use User.update() to trigger this function.
    If user_donor_tier is updated and a partner is set, the partner's partner_donor_tier is updated as well.

    Arguments
    ---------
    user_id: int
    kwargs (column=value):
        bot_enabled: bool
        dnd_mode_enabled: bool
        donor_tier: int
        energy_full_time: datetime UTC aware
        energy_max: int
        helper_context_enabled: bool
        helper_profile_enabled: bool
        helper_profile_ready_commands_visible: bool
        helper_raid_enabled: bool
        helper_raid_compact_mode_enabled: bool
        helper_raid_names_enabled: bool
        helper_upgrades_enabled: bool
        idlucks: int
        last_claim_time: datetime UTC aware
        reactions_enabled: bool
        reminder_channel_id: Optional[int] = None
        reminder_claim_enabled: bool
        reminder_claim_last_selection: float
        reminder_claim_message: str
        reminder_custom_message: str
        reminder_daily_enabled: bool
        reminder_daily_message: str
        reminder_energy_enabled: bool
        reminder_energy_last_selection: int
        reminder_energy_message: str
        reminder_shop_enabled: bool
        reminder_shop_message: str
        reminder_vote_enabled: bool
        reminder_vote_message: str
        reminders_as_embed: bool
        reminders_daily_offset: float
        reminders_slash_enabled: bool
        time_compressors_used: int
        time_speeders_used: int
        tracking_enabled: bool

    Raises
    ------
    sqlite3.Error if something happened within the database.
    NoArgumentsError if no kwargs are passed (need to pass at least one)
    Also logs all errors to the database.
    """
    table = 'users'
    function_name = '_update_user'
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
        kwargs['user_id'] = user.user_id
        sql = f'{sql} WHERE user_id = :user_id'
        cur.execute(sql, kwargs)
        if 'user_donor_tier' in kwargs and user.partner_id is not None:
            partner = await get_user(user.partner_id)
            await partner.update(partner_donor_tier=kwargs['user_donor_tier'])
    except sqlite3.Error as error:
        await errors.log_error(
            strings.INTERNAL_ERROR_SQLITE3.format(error=error, table=table, function=function_name, sql=sql)
        )
        raise


async def insert_user(user_id: int) -> User:
    """Inserts a record in the table "users".

    Returns
    -------
    User object with the newly created user.

    Raises
    ------
    sqlite3.Error if something happened within the database.
    Also logs all errors to the database.
    """
    function_name = 'insert_user'
    table = 'users'
    columns = ''
    values = [user_id,]
    for activity, default_message in strings.DEFAULT_MESSAGES_REMINDERS.items():
        columns = f'{columns},{strings.ACTIVITIES_COLUMNS[activity]}_message'
        values.append(default_message)
    sql = f'INSERT INTO {table} (user_id{columns}) VALUES ('
    for value in values:
        sql = f'{sql}?,'
    sql = f'{sql.strip(",")})'
    try:
        cur = settings.DATABASE.cursor()
        cur.execute(sql, values)
    except sqlite3.Error as error:
        await errors.log_error(
            strings.INTERNAL_ERROR_SQLITE3.format(error=error, table=table, function=function_name, sql=sql)
        )
        raise
    user = await get_user(user_id)

    return user