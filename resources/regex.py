# regex.py

import re


# --- User data extraction ---
USER_ID_FROM_ICON_URL = re.compile(r"avatars\/(.+?)\/")
USERNAME_FROM_EMBED_AUTHOR = re.compile(r"^(.+?) —")
NAME_FROM_MESSAGE = re.compile(r"\s\*\*(.+?)\*\*\s")
NAME_FROM_MESSAGE_START = re.compile(r"^\*\*(.+?)\*\*\s")


# --- User command detection ---)
COMMAND_CLAIM = re.compile(r"\bclaim\b")
COMMAND_CLAN_LIST = re.compile(r"(?:\bguild\b|\bclan\b)\s+\blist\b")
COMMAND_DAILY = re.compile(r"\bdaily\b")
COMMAND_DONATE = re.compile(r"(?:\bdonate\b|\bdonator\b|\bpatreon\b)")
COMMAND_PAYDAY = re.compile(r"(?:\bpd\b|\bpayday\b)")
COMMAND_PROFILE = re.compile(r"(?:\bp\b|\bprofile\b|\bstats\b)")
COMMAND_RAID = re.compile(r"\braid\b")
COMMAND_REQUEST = re.compile(r"\brequest\b")
COMMAND_TEAMRAID = re.compile(r"\bteamraid\b")
COMMAND_USE_ENERGY_ITEM = re.compile(r"\buse\b\s+\benergy\b\s+\b(drink|galloon|glass)\b")
COMMAND_USE_TIME_SPEEDER = re.compile(r"\buse\b\s+\btime\b\s+\bspeeder\b")
COMMAND_UPGRADES_OVERVIEW = re.compile(r"\bupgrades?\b\s*$")
COMMAND_VOTE = re.compile(r"\bvote\b")
COMMAND_WORKER_HIRE = re.compile(r"(?:\broll\b|(\bwo(?:rkers?)?\b\s+\bhire\b))")
COMMAND_WORKER_STATS = re.compile(r"\bwo(?:rkers?)?\b")