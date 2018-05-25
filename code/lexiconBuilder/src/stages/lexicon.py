import csv

import pymongo


class LoadLexicon(object):
    def __init__(self, client_url, lexicon_target_database, lexicon_target_collection, lexiconFile):
        client = pymongo.MongoClient(client_url)
        self.targetCol = client[lexicon_target_database][lexicon_target_collection]
        self.lexiconFile = lexiconFile

    def run(self):
        with open(self.lexiconFile, 'r') as f:
            reader = csv.reader(f, delimiter='\t')
            # skip header
            next(reader)
            for row in reader:
                self.targetCol.update({'_id': row[0]},
                                      {'positive': float(row[1]), 'negative': float(row[2]), 'neutral': float(row[3])},
                                      upsert=True)
