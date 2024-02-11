# regex.py

import re


# --- User data extraction ---
USER_ID_FROM_ICON_URL = re.compile(r"(?:avatars|users)\/(.+?)\/")
USERNAME_FROM_EMBED_AUTHOR = re.compile(r"^(.+?) —")
NAME_FROM_MESSAGE = re.compile(r"\s\*\*(.+?)\*\*\s")
NAME_FROM_MESSAGE_START = re.compile(r"^\*\*(.+?)\*\*\s")


# --- User command detection ---)
COMMAND_ACTIVITIES = re.compile(r"(?:\bactivities\b|\bact\b|\ba\b)")
COMMAND_BOOSTS = re.compile(r"\bboosts?\b")
COMMAND_CLAIM = re.compile(r"(?:\bclaim\b|\bcl\b)")
COMMAND_CLAN_LIST = re.compile(r"(?:\bguild\b|\bclan\b)\s+\blist\b")
COMMAND_CLAN_SEALS = re.compile(r"(?:\bguild\b|\bclan\b)\s+\bseals?\b")
COMMAND_DAILY = re.compile(r"\bdaily\b")
COMMAND_DONATE = re.compile(r"(?:\bdonate\b|\bdonator\b|\bpatreon\b)")
COMMAND_HAL_TRICKORTREAT = re.compile(r"\bhal(?:loween)?\b\s+(?:\btrickortreat\b|\btot\b)")
COMMAND_INVENTORY = re.compile(r"(?:\binventory\b|\binv\b|\bi\b)")
COMMAND_OPEN = re.compile(r"\bopen\b\s+\b.+\b")
COMMAND_PAYDAY = re.compile(r"(?:\bpd\b|\bpayday\b|\bpaytravel\b)")
COMMAND_PROFILE = re.compile(r"(?:\bp\b|\bprofile\b|\bstats\b)")
COMMAND_RAID = re.compile(r"\braid\b")
COMMAND_REQUEST = re.compile(r"(?:\bre\b|\brequest\b)")
COMMAND_SHOP = re.compile(r"\bshop\b")
COMMAND_TEAMRAID = re.compile(r"\bteamraid\b")
COMMAND_USE_BOOST = re.compile(r"(?:\buse\b|\bconsume\b|\bconsoom\b).+(?:\bpopper\b|\bboost\b)")
COMMAND_USE_CHRISTMAS_BELL = re.compile(r"(?:\buse\b|\bconsume\b|\bconsoom\b)\s+\bchristmas\b\s+\bbell\b")
COMMAND_USE_ENERGY_ITEM = re.compile(r"(?:\buse\b|\bconsume\b|\bconsoom\b)\s+\benergy\b")
COMMAND_USE_GUILD_NAME_CHANGER = re.compile(r"(?:\buse\b|\bconsume\b|\bconsoom\b)\s+\bguild\b\s+\bname\b\s+\bchanger\b")
COMMAND_USE_TIME_ITEM = re.compile(r"(?:\buse\b|\bconsume\b|\bconsoom\b)\s+\btime\b")
COMMAND_UPGRADES_OVERVIEW = re.compile(r"\bupgrades?\b\s*$")
COMMAND_VOTE = re.compile(r"\bvote\b")
COMMAND_WORKER_HIRE = re.compile(r"(?:\broll\b|(\bwo(?:rkers?)?\b\s+\bhire\b|\buse\b\s+\bcandy\b\s+\bapple\b))")
COMMAND_WORKER_STATS = re.compile(r"\bwo(?:rkers?)?\b")