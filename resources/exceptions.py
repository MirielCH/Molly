#exceptions.py
"""Contains custom exceptions"""


class NoArgumentsError(ValueError):
    """Custom exception for when no arguments are passed to a function"""
    pass


class NoDataFoundError(Exception):
    """Custom exception for when no data is returned from the database"""
    pass


class RecordExistsError(Exception):
    """Custom exception for when a database record is supposed to be deleted but is not"""
    pass


class FirstTimeUserError(Exception):
    """Custom exception for when no user record is found in the database"""
    pass


class InvalidTimestringError(ValueError):
    """Custom exception for when a timestring is not valid."""
    pass


class EnergyFullTimeOutdatedError(ValueError):
    """Custom exception for when user_settings.energy_full_time lies in the past."""
    pass


class EnergyFullTimeNoneError(ValueError):
    """Custom exception for when user_settings.energy_full_time is None."""
    pass