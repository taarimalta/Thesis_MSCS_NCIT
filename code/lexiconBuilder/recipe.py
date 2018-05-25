import logging as log
import os

import pymongo

log.getLogger().setLevel(log.DEBUG)
log.basicConfig(format='%(asctime)s %(levelname)s: %(message)s')

client_url = 'mongodb://localhost:27017/'


def colExists(dbName, colName):
    client = pymongo.MongoClient(client_url)
    return dbName in client.database_names() and colName in client[dbName].collection_names()


def fileExists(fileName):
    return os.path.isfile(fileName)


def loadInitialLexicon(database, collection, lexiconFile):
    from src.stages.lexicon import LoadLexicon

    LoadLexicon(client_url, database, collection, lexiconFile).run()


def wordCount(sourceDatabase, sourceCollection, targetDatabase,
              targetCollection):
    from src.stages.word_count import WordCount

    WordCount(client_url, sourceDatabase, sourceCollection, targetDatabase, targetCollection).run()


def analyseSentiment(sourceDatabase, sourceCollection, targetDatabase,
                     targetCollection, lexiconDatabase, primaryLexicon,
                     secondaryLexicon, group):
    from src.stages.sentiment_analysis import SentimentAnalyse

    SentimentAnalyse(client_url, sourceDatabase, sourceCollection, targetDatabase, targetCollection, None,
                     lexiconDatabase, primaryLexicon,
                     secondaryLexicon, group).run()


def classCounts(sourceDatabase, sourceCollection, targetDatabase, targetCollection):
    from src.stages.word_polarity import AssignClassCounts

    AssignClassCounts(client_url, sourceDatabase, sourceCollection, targetDatabase, targetCollection).run()


def wordLikelihood(sourceDatabase, sourceCollection, targetDatabase,
                   targetCollection):
    from src.stages.word_polarity import AssignLikelihood

    AssignLikelihood(client_url, sourceDatabase, sourceCollection, targetDatabase, targetCollection).run()


def buildNewLexicon(sourceDatabase, sourceCollection, targetDatabase,
                    targetCollection):
    from src.stages.word_polarity import BuildLexicon

    BuildLexicon(client_url, sourceDatabase, sourceCollection, targetDatabase, targetCollection).run()


def prep(name, grams):
    SOURCE_DB = 'comments'
    CHECKLIST_COL = 'checklist_with_groups_and_test'
    PREP_DB = 'prep_ngrams'
    COOK_DB = name
    LEXICON_COL = 'lexicon'
    TOKENS_COL_PRE = 'pre_tokens_gram_{0}'
    TOKENS_COL = 'tokens'
    WORD_COUNT_COL = 'word_count_gram_{0}'
    GRAMS = grams
    LEXICON_FILE = '../../resources/seedLexicons/emoji_lexicon.tsv'

    # Load Initial Lexicon to Prep DB

    checklistCol = CHECKLIST_COL

    prepDb = PREP_DB
    targetDb = prepDb
    targetCol = LEXICON_COL
    lexiconFile = LEXICON_FILE
    if not colExists(targetDb, targetCol):
        log.info('Loading initial lexicon to {0}-{1}'.format(targetDb, targetCol))
        loadInitialLexicon(targetDb, targetCol,
                           lexiconFile=lexiconFile)
    # Tokenize N Grams
    sourceDb = SOURCE_DB
    sourceCol = checklistCol
    targetDb = targetDb  # unchanged
    for i in range(GRAMS):
        targetCol = TOKENS_COL_PRE.format(i + 1)
        if not colExists(targetDb, targetCol):
            log.info('Tokenizing to {0}-{1}'.format(targetDb, targetCol))
            from src.stages.tokenize import TokenizeNgrams
            TokenizeNgrams(client_url, sourceDb, sourceCol, targetDb, targetCol, grams=i + 1).run()

    # Get word count of Ngrams
    sourceDb = targetDb
    targetDb = targetDb  # unchanged

    for i in range(GRAMS):
        sourceCol = TOKENS_COL_PRE.format(i + 1)
        targetCol = WORD_COUNT_COL.format(i + 1)
        if not colExists(targetDb, targetCol):
            log.info('Counting words to {0}-{1}'.format(targetDb, targetCol))
            wordCount(sourceDb, sourceCol, targetDb, targetCol)

    # Load lexicon to cook db for processing
    targetDb = COOK_DB
    targetCol = LEXICON_COL
    lexiconFile = LEXICON_FILE
    if not colExists(targetDb, targetCol):
        log.info('Loading initial lexicon to {0}-{1}'.format(targetDb, targetCol))
        loadInitialLexicon(targetDb, targetCol,
                           lexiconFile=lexiconFile)

    # Clean up tokens based on count and TF_IDF distribution
    sourceDb = SOURCE_DB
    sourceCol = CHECKLIST_COL
    targetDb = COOK_DB
    targetCol = TOKENS_COL
    lexiconCol = LEXICON_COL
    wordCountDb = PREP_DB
    wordCountCols = [WORD_COUNT_COL.format(i + 1) for i in range(GRAMS)]
    if not colExists(targetDb, targetCol):
        log.info('Clean up words to {0}-{1}'.format(targetDb, targetCol))
        from src.stages.tokenize import WordFrequencyFilterNGrams
        WordFrequencyFilterNGrams(client_url, sourceDb, sourceCol, targetDb, targetCol, wordCountDb, wordCountCols, 3,
                                  lexiconCol).run()


def cook(name, iterations=10, group=None):
    sourceDatabase = name
    workDatabase = name
    lexiconCollection = 'lexicon'
    primaryLexiconCollection = lexiconCollection
    commentSourceDB = sourceDatabase
    commentSourceCol = 'tokens'

    for i in range(iterations):
        log.info("Starting stage {0}".format(i))
        databaseName = workDatabase

        sentimentsCollection = 'tokens_and_sentiments_{0}'.format(i)
        log.info('Writing sentiment analysis of {0}-{1} to {2}-{3} using lexicon {4}-{5}'.format(
            commentSourceDB, commentSourceCol, databaseName, sentimentsCollection, sourceDatabase, lexiconCollection
        ))
        analyseSentiment(commentSourceDB, commentSourceCol, databaseName, sentimentsCollection, sourceDatabase,
                         primaryLexicon=primaryLexiconCollection, secondaryLexicon=lexiconCollection, group=group)

        sourceDatabase = databaseName
        classCountsCollection = 'class_counts_{0}'.format(i)
        log.info('Writing total word scores to {0}-{1}'.format(databaseName, classCountsCollection))
        classCounts(sourceDatabase, sentimentsCollection, databaseName, classCountsCollection)

        likelihoodCollection = 'likelihood_{0}'.format(i)
        log.info('Computing word likelihood to {0}-{1}'.format(databaseName, likelihoodCollection))
        wordLikelihood(sourceDatabase, classCountsCollection, databaseName, likelihoodCollection)

        lexiconCollection = 'lexicon_{0}'.format(i)
        log.info('Building lexicon  to {0}-{1}'.format(databaseName, lexiconCollection))
        buildNewLexicon(databaseName, likelihoodCollection, databaseName, lexiconCollection)

    log.info("Done")


if __name__ == "__main__":
    experiment = 'run_experiment_check'

    prep(experiment, 3)
    cook(experiment, 20)
