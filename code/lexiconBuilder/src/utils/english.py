import csv

_ENGLISH_DICT = {
    'WORDLIST': set(),
    'MIN_WORD_LENGTH': 3
}


def countEnglishWords(englishWordListFile: str, tokens: list):
    def loadEnglishWords():
        with open(englishWordListFile, 'r') as f:
            reader = csv.reader(f, delimiter='\t')
            for row in reader:
                if len(row[0]) >= _ENGLISH_DICT['MIN_WORD_LENGTH']:
                    _ENGLISH_DICT['WORDLIST'].add(row[0])

    if not _ENGLISH_DICT['WORDLIST']:
        loadEnglishWords()

    count = 0
    for t in tokens:
        if len(t) >= _ENGLISH_DICT['MIN_WORD_LENGTH'] and t in _ENGLISH_DICT['WORDLIST']:
            count += 1

    return count
