import pymongo
import regex as re
from nltk import ngrams as ng

from src.utils.regex_util import get_emoji_regexp

"""Cleaners"""


def cleanUnicodeSpace(text: str):
    return text.replace('\u200d', ' ')


def cleanEnglishPunctuations(text, removePurnabiriam):
    if removePurnabiriam:
        return re.sub('\W+', ' ', text)

    # To not allow removing full stop. Nepali Full stop was found to be used instead of ा vowel
    else:
        ret = re.sub('^।\w+', ' ', text)
        return re.sub('।+', '।', ret)


def cleanDoubleNonWords(text):
    # return str
    return re.sub('[^\w ]+(?=[^\w ]+)', ' ', text)


def cleanPurnabiram(text):
    return re.sub('।+', ' ', text)


def cleanWhiteSpaces(text):
    ret = re.sub('[\t\n\r]+', ' ', text)
    ret = re.sub('\s\s+', ' ', ret)
    return ret


def cleanNumbers(text):
    ret = re.sub('[१२३४५६७८९०]+', ' ', text)
    return ret


def clean(text: str, removePurnabiram):
    ret = text
    ret = cleanUnicodeSpace(ret)
    emoticons = getEmoticons(ret)
    ret = cleanEnglishPunctuations(ret, removePurnabiram) + ' '.join(emoticons)
    ret = cleanNumbers(ret)
    ret = cleanWhiteSpaces(ret)
    # ret = cleanDoubleNonWords(ret)
    return ret.strip()


"""Tokenize"""


def getEmoticons(text: str):
    emoticons = []
    for emoticonObj in re.finditer(get_emoji_regexp(), text):
        emoticons += emoticonObj.group(0)

    return emoticons


def getTokens(text: str, wordList=None):
    """If wordlist is not specified, this method simply tokenizes with non devanagari characters.
     It also appends emoticons found

        If wordlist is specified, this method will check if tokens have '।' (Nepali fullstop).
        It will replace nepali fullstop with ा vowel and see if the obtained word exists.
        If the word exists, it is added to the tokens.
        If the word does not exist in the wordlist, the word is split using '।' (Nepali fullstop) and further tokenized
    """
    splitsTemp = re.split('[^\u0900-\u097F]+', text)

    if wordList is not None:
        splits = []

        for w in splitsTemp:
            if '।' in w:
                corrected = re.sub('।+', 'ा', w)
                if corrected in wordList:
                    splits.append(corrected)
                else:
                    w = clean(w, True)
                    splits = splits + getTokens(w, wordList=None)
            else:
                splits.append(w)
    else:
        splits = splitsTemp

    emoticons = getEmoticons(text)

    tokens = splits + emoticons

    return tokens


def getNgrams(text: str, grams):
    splits = []

    # Here, the text is split into sentences first. Second, the sentences are tokenized. Lastly, the sentences are
    # stripped of multiple whitespaces
    for s in re.split('[^\w\s]|[\n\r]+', text):
        tokens = [t.strip() for t in re.split('[^\u0900-\u097F]+', s) if t.strip()]
        if len(tokens) >= grams:
            splits += ['#'.join(g) for g in ng(tokens, grams)]

    emoticons = getEmoticons(text)

    tokens = splits + emoticons

    return tokens


class TokenizeNgrams(object):
    """

    - Tokenize without considering that Nepali fullstop is used instead of ा vowel
    - Find all words using word count
    - Tokenize again considering that Nepali fullstop is used instead of ा vowel.
    This time, check if replacing । with a ा forms a word. Use word count earlier for reference.
    If a word is formed keep that word, otherwise split

    """

    def __init__(self, client_url, sourceDatabaseStr, sourceCollectionStr, targetDatabaseStr, targetCollectionStr,
                 grams=1):
        client = pymongo.MongoClient(client_url)
        self.sourceCol = client[sourceDatabaseStr][sourceCollectionStr]
        self.targetCol = client[targetDatabaseStr][targetCollectionStr]
        self.grams = grams

    @staticmethod
    def getWordStat(tokens: list):
        ret = {}

        from collections import Counter
        counter = Counter(tokens)

        del counter['']

        ret['words'] = list(counter.keys())
        ret['counts'] = counter
        ret['total'] = sum(counter.values())
        return ret

    def run(self):
        removePurnabiram = False

        cleanSentences = (
            (clean(commentDoc['text'], removePurnabiram), commentDoc['group'] if 'group' in commentDoc else 0) for
            commentDoc in
            self.sourceCol.find({'checks.devanagari': True, 'checks.latin': False, 'isTest': False}))

        self.targetCol.insert_many(
            {**self.getWordStat(getNgrams(sentence, self.grams)), **{'group': group}} for sentence, group in
            cleanSentences)


class WordFrequencyFilterNGrams(object):
    """
        - Tokenizes Comments
        - Tokenizes based on token count / word count
        - If 3 grams are used, first 3 grams tokens are checked in every sentence and if found the portion is removed.
        Then the same is done for 2 gram tokens and finally for 1 gram
        - Only those grams that are frequent are used. For example using TF_IDF and document count filters

    """
    MIN_DOC_COUNT = 32  # spell check
    MIN_TF_IDF = 8
    MAX_TF_IDF = 10

    def __init__(self, client_url, sourceDatabaseStr, sourceCollectionStr, targetDatabaseStr, targetCollectionStr,
                 wordCountDbStr,
                 wordCountColStrs, grams, lexiconCollectionStr):
        client = pymongo.MongoClient(client_url)
        self.sourceCol = client[sourceDatabaseStr][sourceCollectionStr]
        self.targetCol = client[targetDatabaseStr][targetCollectionStr]
        # dictionary of wordCount collections indexed by gram
        self.wordCountCols = {(g + 1): client[wordCountDbStr][wordCountColStrs[g]] for g in range(grams)}

        self.grams = grams
        self.wordList = {1: set(), 2: set(), 3: set()}
        self.lexiconCol = client[targetDatabaseStr][lexiconCollectionStr]
        self.populateWordList()

    def populateWordList(self):
        lexiconWords = set([doc['_id'] for doc in self.lexiconCol.find()])

        for gram, col in self.wordCountCols.items():
            self.wordList[gram] = set([doc['_id'] for doc in col.find(
                {'TF_IDF': {'$gt': self.MIN_TF_IDF, '$lt': self.MAX_TF_IDF}, 'documents': {'$gt': self.MIN_DOC_COUNT}},
                {'_id': 1})]).union(lexiconWords)

    def popNgrams(self, words, ngram):
        """
        Takes a list of words and list of search words and returns a list of tuples and the number of search words found
        :param words: List of words to search in
        :param ngram: The list of words to search in words
        :return: list of tuples that represent the words split by ngrams
        """
        if ngram and words:
            index = self.find(words, ngram)
            if index > -1:
                popped = 1
                slice1 = words[0:index]
                slice2 = [None] * len(ngram)
                slice3, p = self.popNgrams(words[index + len(ngram):len(words)], ngram)
                popped = popped + p

                return slice1 + slice2 + slice3, popped
            else:
                return words, 0
        else:
            return words, 0

    def getSentences(self, text):

        # Aakar Issue correction
        text = text.replace('[^\u0900-\u097F]+', '    ')
        splitsTemp = re.split('[^\u0900-\u097F]+', text)
        for w in splitsTemp:
            if '।' in w:
                corrected = re.sub('।+', 'ा', w)
                if corrected in self.wordList[1]:
                    text = text.replace(w, corrected)

        # sentences
        return [s.strip() for s in re.split('[^\w\s]|[\n\r]+', text)]

    @staticmethod
    def getWords(sentence):
        return [t.strip() for t in re.split('[^\u0900-\u097F]+', sentence) if t.strip()]

    @staticmethod
    def find(haystack, needle):
        """Return the index at which the sequence needle appears in the
        sequence haystack, or -1 if it is not found, using the Boyer-
        Moore-Horspool algorithm. The elements of needle and haystack must
        be hashable.

        # >>> find([1, 1, 2], [1, 2])
        1

        Source: https://codereview.stackexchange.com/questions/19627/finding-sub-list
        """
        h = len(haystack)
        n = len(needle)
        skip = {needle[i]: n - i - 1 for i in range(n - 1)}
        i = n - 1
        while i < h:
            for j in range(n):
                if haystack[i - j] != needle[-j - 1]:
                    i += skip.get(haystack[i], n)
                    break
            else:
                return i - n + 1
        return -1

    def getNgrams(self, words, gram):

        if len(words) >= gram:
            ngrams = [g for g in ng(words, gram)]
            ngramsFound = set(['#'.join(ngram) for ngram in ngrams if (None not in ngram)]).intersection(
                self.wordList[gram])
            return ngramsFound

        return []

    def run(self):
        removePurnabiram = False
        cleanText = ((clean(commentDoc['text'], removePurnabiram), commentDoc['group'] if 'group' in commentDoc else 0)
                     for commentDoc in
                     self.sourceCol.find({'checks.devanagari': True, 'checks.latin': False, 'isTest': False}))

        inserts = []

        for text, group in cleanText:

            sentences = self.getSentences(text)
            segments = [tuple(self.getWords(s)) for s in sentences if len(s) > 0]

            for seg in segments:
                tokens = getEmoticons(text)

                words = list(seg)
                # Check for each ngram
                for length in range(self.grams, 0, -1):

                    ngrams = self.getNgrams(words, length)

                    if ngrams:
                        for ngram in ngrams:
                            tokens.append(ngram)

                inserts.append({'words': tokens, 'group': group})

        self.targetCol.insert_many(inserts)

    def runMethod1(self):
        """ This was the previous run method. The current method was observed to give more accurate results"""
        removePurnabiram = False
        cleanText = ((clean(commentDoc['text'], removePurnabiram), commentDoc['group'] if 'group' in commentDoc else 0)
                     for commentDoc in
                     self.sourceCol.find({'checks.devanagari': True, 'checks.latin': False}))

        inserts = []

        for text, group in cleanText:
            tokens = set(getEmoticons(text))
            sentences = self.getSentences(text)
            segments = [tuple(self.getWords(s)) for s in sentences if len(s) > 0]

            for seg in segments:
                words = list(seg)
                # Check for each ngram
                for length in range(self.grams, 0, -1):

                    ngrams = self.getNgrams(words, length)

                    if ngrams:
                        for ngram in ngrams:
                            words, popped = self.popNgrams(words, ngram.split('#'))

                            if popped > 0:
                                tokens.add(ngram)

            inserts.append({'words': tokens, 'group': group})

        self.targetCol.insert_many(inserts)
