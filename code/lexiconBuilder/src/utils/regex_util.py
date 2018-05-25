import regex as re

_EXPRESSIONS = {}

SPECIAL_CHARS = r"~`!@#$%^&*()_-+={}[]:>;',</?*-+"

# Source PLOS EMOJI
EMOTICONS = r'┊🎎▃♨🔅🏧✰🌼😙🔔🎁🆔◤❤💞🎉💐💃💙🏆🎊🎈💖😚💛🎆😘🚜👑💋🚹🐟🐭💘💟🎇😍🍓♡🇷📄🚳💓🍹💑♥☺💗🚴💚💜🌸↿🐌🎷↾😊💝🚨⛳💕😋🎀😻👳⚽🇪📴◢🎂' \
            r'🇩💿😗🌗🌖👸🐾😛🌹🚿💡❅🍉🎃🇮🌍🌓🌙😇🐮🐥🐰🎺¦⭐🇹🌘🌔🐶🏊😽⚓🌱👚🚣🗻🌻😀👌🎓🌒🐪💎🙌🌞🐏😃🌕🚼◆♌🚐✘💪🔆🌛🌺🍂┛🎾🇺♔🍸🌷🌾🌰⌒🎶🍴🆗♪' \
            r'🎄🏈➕💼🌠🌴🏄♩🗼👍⛄🚬🐒👏🌌🐤🎸🌈👨🐱🍻🇸❄🎵🙆💫🌊👙🏠🏁💌🌜🌇🏉💒🌉✎🚄▲⛵👤👢🍺😎🚀🌳👰🙋⛔😌🍁💍🐵🎤🐯🐣🔝👄🇫♻💦♧🎢🍍⬅☀🌚▬✌😉👭⛺🎒' \
            r'👅🙊🍦🌑🐧😜⇨○🍼🐗♦🍚⚪⛅😁🍰🌽🐨🎋🐜🌋┓┣🗿🐻👯⏰◠╝🏡🍌💄◕👶🙈💊📷✊📹👞☆🎮👈😝👵😄🐬🏩📢🐦🙏🍕🍊👟🐐🎽✈🎧🐠👋😸😆✅🏃🔊🍆❀🐎▽👕💳' \
            r'🇱📞📃💷🔛🇲🔴😺🍜🍷👉🌃⬇💏💅🐙♕🌲🍘🏂👡🌿✿🍩💨💵🍃📺🚲🎿🎠💤🐷🍬💬🍵🆒📣┃👾💉👛╦🌅👠😼🎹🚵╗✨🐍🍅🐩👣│✏♣📚🙉👼🔐👖🇴👔🐫☛🚤🔚🎻👝' \
            r'✞🔭🇼ⓁⒺ😏🙀🌟🎼💇💁👆✧🌏🍎🌎🎅🗽🍪👽🍒✖➤☝☁📱📻🔵✪♠🍟🍧🍭🐔🐆♢👓🐹🐈🏰╚🈹🎥☔♫✓⬆🎡🍀★🍙®🎬🐄🍔🔜🚓❌✔😮🍇◀🔮🇬🇧🐛😈🐼◉👫🏀💰🍑💻🚂' \
            r'╔🏥✉◂📰📶🗾🔶🏤🎩Ⓜ👇♬☕🍋💲📲🌂❥👗👜⚫💢🚗📝👴🐇🐕✒🚢❒👊👻🐚🐺◄◡👥🐡🎪👷🔈📡🅰😂💆▸🍨🐝▶╠💭🐢╩⌚🆓🐋💺☻🏨🔸👒❕▪☼😬🔙🌵😱🚌🌝♛🔒📓☉📕😅' \
            r'⚡━●🌁🎐📖🚺🎨🔷📅►➜╭💸🍐🏢🐉🍫⛽🐖💥➡║🐂🐀😹🙇─👧🔥➨👦🌆🔹🐳🍖╮✋🍲🛀⛪🚁📗♂🔩🌄🐅♮😯😥💯🐽⇧©🍝☞📵🏯📍⏩╥☑🌀❗👱⌛📀↪�😵🃏▼🚦🔓🐊😟' \
            r'🚑🆘🚍🔪🐴❓🚘🍏👩🔱🚋🏪☷👀🍗✦👹❁⛲🍤⠀🍯🍞♚📒🍛🚙🐓🍳🐘😳═▓😢💣☯💶❊🎭▁🚕☎╱⇩▂🍠۩✳❔✩✯╣┼🐃🍄⏳☂↳🚔۞☾📥🔦☮◞🚥🔄☄☨╯👪😰👐▒█☠⚾🔞░🍡🙎' \
            r'🐲◟👬╰😧⚠😲▄🚚😴😪😓🐸🚖➰🔌😭🏇Ⓐ♎🔨🍢💩😞🍮➔💔┐📯🅾▐👂╬😨😶🚶▀😫😔💂😖💧🐑😷😡👺🚛💴👎🔫🚩🙅💀😤😣□🏫🍣▌■🐁😠😑🍱🙍😾🍈👮┳┻😩😦😿😒🔧😐😕📌🚫✂￼🔋☹👿┈🍥☐ '


def get_emoji_regexp():
    # Build emoji regexp once
    if 'EMOJI_REGEXP' not in _EXPRESSIONS:
        pattern = u'[' + EMOTICONS + u']'
        _EXPRESSIONS['EMOJI_REGEXP'] = re.compile(pattern)

    return _EXPRESSIONS['EMOJI_REGEXP']


def get_emoji_old_regexp():
    """Returns compiled regular expression that matches emojis defined in
    ``emoji.UNICODE_EMOJI_ALIAS``. The regular expression is only compiled once.
    """

    import emoji

    # Build emoji regexp once
    if 'EMOJI_REGEXP' not in _EXPRESSIONS:
        # Sort emojis by length to make sure multi-character emojis are
        # matched first
        emojis = sorted(emoji.EMOJI_UNICODE.values(), key=len,
                        reverse=True)

        specialCharRegex = get_special_char_regexp()
        whiteSpaceRegex = get_white_space_regexp()

        specialCharOrWhiteSpace = orRegex(specialCharRegex, whiteSpaceRegex)

        pattern = u'[' + u''.join(re.sub(specialCharOrWhiteSpace, '', re.escape(u)) for u in emojis) + u']'
        _EXPRESSIONS['EMOJI_REGEXP'] = re.compile(pattern)

    return _EXPRESSIONS['EMOJI_REGEXP']


def get_latin_regexp():
    LATIN_RANGE = r'[0-9a-zA-Z]'

    if 'LATIN_REGEXP' not in _EXPRESSIONS:
        _EXPRESSIONS['LATIN_REGEXP'] = re.compile(LATIN_RANGE)

    return _EXPRESSIONS['LATIN_REGEXP']


def get_devanagari_regexp():
    DEVANAGARI_RANGE = r'[\u0900-\u097F]'

    if 'DEVANAGARI_REGEXP' not in _EXPRESSIONS:
        _EXPRESSIONS['DEVANAGARI_REGEXP'] = re.compile(DEVANAGARI_RANGE)

    return _EXPRESSIONS['DEVANAGARI_REGEXP']


def get_special_char_regexp():
    if 'SPECIAL_REGEXP' not in _EXPRESSIONS:
        pattern = u'[' + u''.join(re.escape(u) for u in SPECIAL_CHARS) + u']'
        _EXPRESSIONS['SPECIAL_REGEXP'] = re.compile(pattern)

    return _EXPRESSIONS['SPECIAL_REGEXP']


def get_white_space_regexp():
    whiteSpaceChars = r'\s'
    if 'WHITE_SPACE_REGEXP' not in _EXPRESSIONS:
        _EXPRESSIONS['WHITE_SPACE_REGEXP'] = re.compile(whiteSpaceChars)

    return _EXPRESSIONS['WHITE_SPACE_REGEXP']


def orRegex(*regexp):
    retPattern = u'|'.join([r.pattern for r in regexp])
    return re.compile(retPattern)
