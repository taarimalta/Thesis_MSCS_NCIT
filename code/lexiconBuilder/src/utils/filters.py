from src.utils.regex_util import get_devanagari_regexp, get_latin_regexp, get_emoji_regexp, orRegex, \
    get_white_space_regexp, get_special_char_regexp

import regex as re


def hasDevanagari(text):
    return hasRegex(text, get_devanagari_regexp())


def hasLatin(text):
    return hasRegex(text, get_latin_regexp())


def hasEmoticon(text):
    return hasRegex(text, get_emoji_regexp())


def hasRegex(text, regExp):
    if re.search(regExp, text):
        return True
    else:
        return False


def hasChecklist(testStr: str, devanagari: bool, latin: bool, emoticon: bool, whiteSpace: bool, specialChar: bool):
    yeses = []
    nos = []

    if devanagari:
        yeses.append(get_devanagari_regexp())
    else:
        nos.append(get_devanagari_regexp())
    if latin:
        yeses.append(get_latin_regexp())
    else:
        nos.append(get_latin_regexp())
    if emoticon:
        yeses.append(get_emoji_regexp())
    else:
        nos.append(get_emoji_regexp())
    if whiteSpace:
        yeses.append(get_white_space_regexp())
    else:
        nos.append(get_white_space_regexp())
    if specialChar:
        yeses.append(get_special_char_regexp())
    else:
        nos.append(get_special_char_regexp())

    yesRegex = orRegex(*yeses) if yeses else None
    noRegex = orRegex(*nos) if nos else None

    ret = True

    if yesRegex:
        ret = ret and hasRegex(testStr, yesRegex)
    if noRegex:
        ret = ret and not hasRegex(testStr, noRegex)

    return ret


def createChecklist(testStr):
    regexes = {'devanagari': get_devanagari_regexp(), 'latin': get_latin_regexp(), 'emoticon': get_emoji_regexp(),
               'whiteSpace': get_white_space_regexp(), 'specialChar': get_special_char_regexp()}

    ret = {}

    for check, value in regexes.items():
        ret[check] = hasRegex(testStr, value)

    return ret
