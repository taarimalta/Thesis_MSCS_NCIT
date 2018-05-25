import csv

import pymongo

KEY_POSITIVE = 'positive'
KEY_NEGATIVE = 'negative'
KEY_AVERAGE = 'average'

LEXICON_PRIMARY = 'PRIMARY'
LEXICON_SECONDARY = 'SECONDARY'
LEXICON_NONE = 'NONE'

WEIGHTS = {LEXICON_PRIMARY: 2.0, LEXICON_SECONDARY: 1.0, LEXICON_NONE: 0.0}


class SentimentAnalyse(object):
    def __init__(self, client_url, sourceDatabaseStr, sourceCollectionStr, targetDatabaseStr, targetCollectionStr,
                 lexiconFile, lexiconDatabase, primaryLexiconCollection, secondaryLexiconCollection, group):
        client = pymongo.MongoClient(client_url)
        self.sourceCol = client[sourceDatabaseStr][sourceCollectionStr]
        self.targetCol = client[targetDatabaseStr][targetCollectionStr]

        self.primary_lexicon = None
        self.secondary_lexicon = None

        self.group = group

        # Lexicon File approach does not work @deprecated
        if lexiconFile:
            self.populateKnownLexicon(lexiconFile)
        else:
            self.populateWithMongoCollection(client, lexiconDatabase, primaryLexiconCollection,
                                             secondaryLexiconCollection)

    def run(self):
        sentiments = []
        # for doc in self.sourceCol.find({'group': {'$in': [self.group * 2, self.group * 2 + 1]}}):
        for doc in self.sourceCol.find():
            avgPols = self.getPolaritiesUsingLexicon(doc['words'])

            if avgPols[0] is not None:
                sentiments.append({'words': doc['words'], KEY_POSITIVE: avgPols[0], KEY_NEGATIVE: avgPols[1],
                                   KEY_AVERAGE: avgPols[2]})

        self.targetCol.insert_many(sentiments)

    def getPolaritiesUsingLexicon(self, words):
        """
        Returns weighted positive, weighted negative and weighted overall

        Note that here weighted overall = (weighted positive - weighted negative)/2 and ranges between -0.5 to 0.5.

        (sum(positivePols)-sum(negativePols))/(sum(positiveWeights)+sum(negativeWeights))
        =(sum(positivePols)-sum(negativePols))/(sum(positiveWeights)+sum(positiveWeights) // Both weigh same
        =(sum(positivePols)-sum(negativePols))/(2*sum(positiveWeights)))
        =(weighted positive - weighted negative)/

        The above is multiplied by 2 to make it fall between -1 and 1

        :param words:
        :return:
        """
        positivePols = []
        negativePols = []

        positiveWeights = []
        negativeWeights = []

        for word in words:
            wordInfo = self.getPolarityInfo(word)

            if wordInfo is not None:
                positivePols.append(wordInfo[KEY_POSITIVE] * WEIGHTS[wordInfo['lexicon']])
                negativePols.append(wordInfo[KEY_NEGATIVE] * WEIGHTS[wordInfo['lexicon']])

                positiveWeights.append(WEIGHTS[wordInfo['lexicon']])
                negativeWeights.append(WEIGHTS[wordInfo['lexicon']])

        if positiveWeights and negativeWeights and sum(positiveWeights) and sum(negativeWeights):
            return sum(positivePols) / sum(positiveWeights), sum(negativePols) / sum(negativeWeights), (
                sum(positivePols) - sum(negativePols)) * 2 / (sum(positiveWeights) + sum(negativeWeights))
        else:
            return None, None, None

    def getPolarity(self, word, polarityType):
        if self.primary_lexicon is None:
            raise Exception("Primary Lexicon not defined")
        elif isinstance(self.primary_lexicon, dict):
            info = self.primary_lexicon[word] if word in self.primary_lexicon else None

            if info is not None:
                return info[polarityType], LEXICON_PRIMARY
            elif self.secondary_lexicon is not None:
                info = self.secondary_lexicon[word] if word in self.secondary_lexicon else None

                if info is not None:
                    return info[polarityType], LEXICON_SECONDARY

            return 0.0, LEXICON_NONE
        else:
            raise Exception("Lexicon is invalid")

    def getPolarityInfo(self, word):
        if self.primary_lexicon is None:
            raise Exception("Primary Lexicon not defined")
        elif isinstance(self.primary_lexicon, dict):
            ret = {}
            info = self.primary_lexicon[word] if word in self.primary_lexicon else None

            if info is None:
                if self.secondary_lexicon is not None:
                    info = self.secondary_lexicon[word] if word in self.secondary_lexicon else None
                    if info is None:
                        return None
                    else:
                        ret['lexicon'] = LEXICON_SECONDARY
                else:
                    return None
            else:
                ret['lexicon'] = LEXICON_PRIMARY

            ret[KEY_POSITIVE] = info[KEY_POSITIVE]
            ret[KEY_NEGATIVE] = info[KEY_NEGATIVE]

            return ret
        else:
            raise Exception("Lexicon is invalid")

    def populateKnownLexicon(self, known_lexicon_str):
        self.primary_lexicon = {}
        with open(known_lexicon_str, 'r') as f:
            reader = csv.reader(f, delimiter='\t')
            # skip header
            next(reader)

            for row in reader:
                self.primary_lexicon[row[0]] = {'positive': float(row[1]), 'negative': float(row[2])}

    def populateWithMongoCollection(self, client, databaseStr, primaryCollectionStr, secondaryCollectionStr):

        self.primary_lexicon = {}
        self.secondary_lexicon = {}

        for doc in client[databaseStr][primaryCollectionStr].find():
            self.primary_lexicon[doc['_id']] = {'positive': float(doc['positive']), 'negative': float(doc['negative'])}

        for doc in client[databaseStr][secondaryCollectionStr].find():
            self.secondary_lexicon[doc['_id']] = {'positive': float(doc['positive']),
                                                  'negative': float(doc['negative'])}
