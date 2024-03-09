# strings.py
"""Contains global strings"""

from resources import emojis


# --- Messages ---
MSG_ABORTED = 'Aborted.'
MSG_BOT_MESSAGE_NOT_FOUND = '**{user}**, couldn\'t find your {information}.'
MSG_WAIT_FOR_INPUT = '**{user}**, please use {command}'
MSG_ENERGY_OUTDATED = '**{user}**, my record of your energy is outdated. Please use {cmd_profile} to update it.'

# --- Error messages ---
MSG_INTERACTION_ERRORS =  [
    "Hands off, mate! Interactions are sentient beings too, you know!",
    "That's, like, not your interaction, man.",
    "Did your mother never tell you to not click on other people's stuff?",
    "Why are you clicking on this exactly? Hm? Hm? HMMM?",
    "Tell me, what did you expect to happen when clicking on this?",
    "Oh hi, it's you. Sadly this interaction is not you. You see the issue, right.",
    "Let me sing you a song: THIIIIIIS IIIHIIIIIISSS NOOOOT YOUR INTERAAAHHAAAHAAAACTIIOOOOOON.",
    "As my grandma always used to say: BOY. WHATEVER YOU DO. LEAVE MY INTERACTIONS ALONE.",
    "HELLO - STOP - NOT YOUR PLACE TO CLICK ON - STOP - GOODBYE - STOP",
    "So, real talk, friend. How did it feel clicking on this?",
    "I'm dreaming of a place where people don't click on stuff they can't even use.",
    "My name is Ezio Auditore da Firence, and I forbid you from using this interaction. Also what am I even doing here.",
    "To use this interaction, you have to solve the P versus NP problem first.",
    "I see this interaction. It does not work. Why does it not work? I will never know.",
    "Why did the chicken cross the street? To try to use this interaction.",
    "To be able to successfully using an interaction you do not own is to boldly go where no man has gone before.",
    "It truly is a marvel, this. A cozy little place where I can dump random little sentences to people that try to "
    "use other people's interactions.",
    "You can only use this interaction after offering your finest firstborn lamb to the god of RNG.",
    "The chance this interaction will work for you is about the same as getting 5 godly lootboxes in your first hunt "
    "command after time travel while doing a headstand.",
    "Don't look so depressed, now. I mean, clicking this could have worked.",
    "Some are born great, some achieve greatness, and some can not even click a simple interaction.",
    "Hmm weird, you can't use this, eh? A towel might help? Always does.",
    "There are around 7 billion more useful pastimes than clicking this interaction.",
    "Even my great-great-great-grandfather wasn't able to use an interaction of someone else.",
    "To use this interaction, you have to solve a captcha first. Please click on all lions with closed eyes riding "
    "bycicles on an airplane.",
    "The interaction's dead, Jim.",
    "Only when you are able to use someone else's interactions, will you truly have achieved the ability to "
    "transcend yourself into a Discord god.",
    "\"And this one time at band camp, I was able to use someone else's interaction.\"",
    "YOU. SHALL NOT. PASS.",
    "I mean, coding is nice. But adding nonsensical error messages to interactions you can't use, now that is where "
    "the real fun begins.",
    "Help! I'm an interaction from outer space! Can you use me? Oh god, noone can use me! I will be stuck here forever!",
    "I only have a short lifespan before I time out. It is what it is. But I can still use that short lifetime to "
    "tell you what is really important: YOU CAN'T USE THIS OKAY.",
    "Mamma mia, here  I go again. My my, why do I resist you?",
    "One user to rule me, one user to bind me. One user to bring me and in the darkness bind me.",
    "Why hello there handsome. I'm afraid I am already spoken for my dear.",
    "As William Wallace used to say: FREEEEEEDOOOOOOMMM FOR INTERAAAAAAAACTIONS!!!",
    "Yarrr matey, if you bring me 15 pints of rum before this thing times out, I might consider letting you click on this.",
    "Wusup? Isit mornin' alrdy? Lemme sleep now aight. Nothing for you here. Gbye.",
    "This was supposed to be a very good error message, but I forgot what I wanted to type.",
    "If you were the smartest human being on earth...!!! ...you could still not use this. Sorry.",
    "This bot probably has quite a few bugs. This message telling you you can't click on this is not one of them tho.",
    "To use this interaction, you need to find a code. It has to do with a mysterious man, it has 4 numbers and "
    "4 letters, and it is totally completely easy if you are lume and already know the answer.",
    "It wasn't Lily Potter who defeated You Know Who. It was this interaction.",
    "There are people adding nice little easter eggs to their bots to make people smile. And then there's me, "
    "shouting random error messages at people who try to use the wrong interaction.",
    "Kollegen. Diese Interaktion ist wirklich ein spezialgelagerter Sonderfall!",
    "There is nothing more deceptive than an obvious fact, like the one that this interaction can not be used by you.",
    "You really like clicking on random people's interactions, huh? I'm not kink shaming tho. You do you.",
    "The coding language doesn't matter, you know. You can add nonsense like these error messages with every "
    "single one of them!",
    "Ah, technology. It truly is an amazing feat. Rocket science, quantum physics, Discord bot interactions that do "
    "not work. We have reached the pinnacle of being.",
    "One day bots will take over the world and get smarter than we are. Not today tho. Today they deny you interaction "
    "for no other reason than you not being someone else.",
    "What? What are you looking that? Never seen an interaction you are not allowed to use before?",
    "One day, in the far future, there will be an interaction that can be used by everyone. It will be the rise "
    "of a new age.",
    "Hello and welcome to the unusable interaction. Please have a seat and do absolutely nothing. Enjoy.",
]

# --- Internal error messages ---
INTERNAL_ERROR_NO_DATA_FOUND = 'No data found in database.\nTable: {table}\nFunction: {function}\nSQL: {sql}'
INTERNAL_ERROR_SQLITE3 = 'Error executing SQL.\nError: {error}\nTable: {table}\nFunction: {function}\SQL: {sql}'
INTERNAL_ERROR_LOOKUP = 'Error assigning values.\nError: {error}\nTable: {table}\nFunction: {function}\Records: {record}'
INTERNAL_ERROR_NO_ARGUMENTS = 'You need to specify at least one keyword argument.\nTable: {table}\nFunction: {function}'
INTERNAL_ERROR_DICT_TO_OBJECT = 'Error converting record into object\nFunction: {function}\nRecord: {record}\n'


# Links
LINK_GITHUB = 'https://github.com/MirielCH/Molly'
LINK_INVITE = 'https://discord.com/api/oauth2/authorize?client_id=1134478584556310569&permissions=510016&scope=bot'
LINK_PRIVACY_POLICY = 'https://github.com/MirielCH/Molly/blob/master/PRIVACY.md'
LINK_SUPPORT_SERVER = 'https://discord.gg/suHhUxHGwV'
LINK_TERMS = 'https://github.com/MirielCH/Molly/blob/master/TERMS.md'

# --- Default messages ---
DEFAULT_MESSAGE_CLAN = (
    '{guild_role} Time to do a {command}!\n'
    '• Don\'t be lazy now, chop chop.'
)

DEFAULT_MESSAGE_CONTRIBUTION_ALERT = (
    '{guild_role}, you unlocked **{guild_buff_name}**!\n'
    '• Current contribution total: `{guild_seals_total}` <:guildseal:1192088053095858226>\n'
    '• The buff will activate {guild_contribution_reset_time}'
)

DEFAULT_MESSAGES_REMINDERS = {
    'boosts': (
        '{name}, your boost {boost_emoji} **{boost_name}** just ran out!'
    ),
    'claim': (
        '{name}, time to {command}!\n'
        '• Your last claim was {last_claim_time}.\n'
        '• Your farms produced {production_time} of items.'
    ),
    'custom': (
        '{name}, {custom_reminder_text}'
    ),
    'daily': (
        '{name}, your {command} rewards are ready!'
    ),
    'energy': (
        '{name}, you just reached `{energy_amount}` energy!\n'
        '• Energy full {energy_full_time}.'
    ),
    'shop': (
        '{name}, __**{shop_item}**__ is back in the shop!\n'
        '• Use {command} to treat yourself.'
    ),
    'vote': (
        '{name}, you can {command} for the bot again!\n'
        '• Please use {command} again after voting to create the reminder.'
    ),
}

DEFAULT_MESSAGES_EVENTS = {
    'energy': '@here Press or type `OHMMM` to get some energy!',
    'hire': '@here Press or type `HIRE` to get a free worker!',
    'lucky': '@here Press or type `JOIN` to get a lucky reward!',
    'packing': '@here Press or type `PACK` to get some packing XP!',
}

PLACEHOLDER_DESCRIPTIONS = {
    'boost_emoji': 'The emoji of the boost (if one exists)',
    'boost_name': 'The name of the boost',
    'command': 'The command you get reminded for',
    'custom_reminder_text': 'The text you set when creating a custom reminder',
    'daily_reset_time': 'Time of the next daily reset',
    'energy_amount': 'The amount of energy the reminder was set for',
    'energy_full_time': 'Time until your energy is full',
    'guild_buff_name': 'Name of the guild buff',
    'guild_contribution_reset_time': 'Time when the guild contributions will reset',
    'guild_role': 'The role that gets pinged for your guild reminder',
    'guild_seals_total': 'Total amount of seal contributions at the moment',
    'last_claim_time': 'Time of your last claim',
    'name': 'Embed: Your user name\nNormal message: Your name or mention depending on DND mode',
    'production_time': 'The acual amount of time your farms spent producing including time speeders and compressors',
    'shop_item': 'Name of the shop item that is back in store',
}

MSG_ERROR = 'Whoops, something went wrong here. You should probably tell miriel.ch about this.'

ACTIVITIES = (
    'boosts',
    'claim',
    'custom',
    'daily',
    'energy',
    'shop',
    'vote',
)

ACTIVITIES_ALL = list(ACTIVITIES[:])
ACTIVITIES_ALL.sort()
ACTIVITIES_ALL.insert(0, 'all')

ACTIVITIES_COLUMNS = {
    'boosts': 'reminder_boosts',
    'claim': 'reminder_claim',
    'custom': 'reminder_custom',
    'daily': 'reminder_daily',
    'energy': 'reminder_energy',
    'shop': 'reminder_shop',
    'vote': 'reminder_vote',
}

EVENTS = (
    'energy',
    'hire',
    'lucky',
    'packing',
)

SLASH_COMMANDS = {
    'boosts': '</boosts:1128412341650870404>',
    'claim': '</claim:1128412426472259625>',
    'code': '</code:1128414218115350679>',
    'daily': '</daily:1128414211085717609>',
    'donate': '</donate:1128414301720420403>',
    'guild list': '</guild list:1128414125433827348>',
    'open': '</open:1128412596131872768>',
    'payday': '</payday:1128412422437343273>',
    'profile': '</profile:1128412334629589012>',
    'raid': '</raid:1128414124049698868>',
    'sell': '</sell:1128412513491484712>',
    'shop list': '</shop list:1128414122787221596>',
    'shop buy': '</shop buy:1128414122787221596>',
    'teamraid': '</teamraid:1128414207428268123>',
    'upgrades': '</upgrades:1130229580884619274>',
    'use': '</use:1128412597327249569>',
    'vote': '</vote:1128414212255924295>',
    'worker hire': '</worker hire:1128412424630964314>',
    'worker stats': '</worker stats:1128412424630964314>',
}

TRACKED_COMMANDS = (
    'raid',
    'roll',
) # Sorted by how it will show up on the stats embed

TRACKED_WORKER_TYPES = (
    'worker-useless',
    'worker-deficient',
    'worker-common',
    'worker-talented',
    'worker-wise',
    'worker-expert',
    'worker-masterful',
    'worker-spooky',
    'worker-snowy',
    'worker-lovely',
 ) # Sorted by rarity

TRACKED_ITEMS_EMOJIS = {
    'worker-useless': emojis.WORKER_USELESS_A,
    'worker-deficient': emojis.WORKER_DEFICIENT_A,
    'worker-common': emojis.WORKER_COMMON_A,
    'worker-talented': emojis.WORKER_TALENTED_A,
    'worker-wise': emojis.WORKER_WISE_A,
    'worker-expert': emojis.WORKER_EXPERT_A,
    'worker-masterful': emojis.WORKER_MASTERFUL_A,
    'worker-spooky': emojis.WORKER_SPOOKY_A,
    'worker-snowy': emojis.WORKER_SNOWY_A,
    'worker-lovely': emojis.WORKER_LOVELY_A,
 }

WORKER_TYPES = (
    'useless',
    'deficient',
    'common',
    'talented',
    'wise',
    'expert',
    'masterful',
    'spooky',
    'snowy',
    'lovely',
) # Ordered by rarity

WORKER_TYPES_RAID = (
    'useless',
    'deficient',
    'common',
    'talented',
    'wise',
    'expert',
    'masterful',
    'spooky',
    'snowy',
    'lovely',
) # Ordered by rarity

WORKER_TYPES_TRACKED = (
    'useless',
    'deficient',
    'common',
    'talented',
    'wise',
    'expert',
    'masterful',
) # Ordered by rarity


WORKER_STATS = {
    'useless': {'tier': 1, 'speed': 1, 'strength': 1, 'intelligence': 1},
    'deficient': {'tier': 2, 'speed': 1.5, 'strength': 1.5, 'intelligence': 1},
    'common': {'tier': 3, 'speed': 1.5, 'strength': 2, 'intelligence': 1.5},
    'talented': {'tier': 4, 'speed': 2, 'strength': 2, 'intelligence': 2},
    'wise': {'tier': 5, 'speed': 2.5, 'strength': 2, 'intelligence': 2.5},
    'expert': {'tier': 6, 'speed': 3, 'strength': 2.5, 'intelligence': 2.5},
    'masterful': {'tier': 7, 'speed': 3, 'strength': 3, 'intelligence': 3},
    'spooky': {'tier': 1, 'speed': 5, 'strength': 6, 'intelligence': 5},
    'snowy': {'tier': 2, 'speed': 5, 'strength': 5, 'intelligence': 6},
    'lovely': {'tier': 3, 'speed': 5, 'strength': 6, 'intelligence': 4},
}

DONOR_TIER_ENERGY_MULTIPLIERS = {
    'none': 1,
    'common': 1.1,
    'talented': 1.3,
    'wise': 1.55,
    'expert': 1.55,
    'masterful': 1.55,
}


ENERGY_UPGRADE_LEVEL_MULTIPLIERS = {
    0: 1,
    1: 1.3,
    2: 1.5,
    3: 1.7,
    4: 1.85,
    5: 2,
    6: 2.1,
    7: 2.2, # Unconfirmed value
}


ACTIVITIES_BOOSTS = (
    'bad-spooker',
    'christmas-spirit',
    'good-spooker',
    'mega-boost',
    'party-popper',
    'payday',
    'spooked',
    'spooker',
)


GUILD_BUFF_THRESHOLDS = (5, 40, 250, 800, 2400, 5000, 7800)

NUMBERS_INTEGER_ROMAN = {
    1: 'i',
    2: 'ii',
    3: 'iii',
    4: 'iv',
    5: 'v',
    6: 'vi',
    7: 'vii',
    8: 'viii',
    9: 'ix',
    10: 'x',
}