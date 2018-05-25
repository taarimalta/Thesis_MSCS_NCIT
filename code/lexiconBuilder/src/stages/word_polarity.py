import math

import numpy as np
import pymongo

NUM_CLASSES = 2
LAPLACE_SMOOTHENING = 0
SMALL_NUMBER = 0.000000001


class AssignClassCounts(object):
    """
    The name of the class is it's lower boundary.

    Multi:
    For 5 classes, the class names are c0,c1,c2,c3,c4

    BiClass:

    The class names are c0,c1

    """

    def __init__(self, client_url, sourceDatabaseStr, sourceCollectionStr, targetDatabaseStr, targetCollectionStr):
        client = pymongo.MongoClient(client_url)
        self.sourceCol = client[sourceDatabaseStr][sourceCollectionStr]
        self.targetCol = client[targetDatabaseStr][targetCollectionStr]
        self.numClasses = NUM_CLASSES
        self.scoreRange = [-1, 1]
        self.laplaceSmoothening = LAPLACE_SMOOTHENING

    @staticmethod
    def argmax(doc):
        # The commented out is the Built in method
        # tempDoc={'positive':doc['positive'],'negative':doc['negative']}

        # f = lambda x: tempDoc[x]

        # Ignoring Neutral Class
        # return max(['positive', 'negative', 'neutral'], key=f)
        # return max(['positive', 'negative'], key=f)

        if doc['positive'] > doc['negative']:
            return 'positive'
        elif doc['negative'] > doc['positive']:
            return 'negative'
        else:
            import random
            coin_flip = ['positive', 'negative']
            return random.choice(coin_flip)

    def lowerBoundary(self, classNum, sRange):
        """
        Lower boundary for class n.. 0 indexed
        :param classNum:
        :param sRange:
        :return:
        """

        return sRange[0] + classNum * self.getClassInterval(sRange)

    def upperBoundary(self, classNum, sRange):
        return sRange[0] + (classNum + 1) * self.getClassInterval(sRange)

    def getClassInterval(self, sRange):
        return (sRange[1] - sRange[0]) * 1.0 / self.numClasses

    def getClassNum(self, score, sRange):
        if score == sRange[1]:
            return self.numClasses - 1
        else:
            return math.floor((score - sRange[0]) / self.getClassInterval(sRange))

    def run(self):
        temp = {}  # For batch updates

        for doc in self.sourceCol.find():
            for w in set(doc['words']):
                if w and len(w) < 50:
                    if w in temp:
                        if doc['positive']:
                            temp[w]['positives'].append(doc['positive'])
                        if doc['negative']:
                            temp[w]['negatives'].append(doc['negative'])
                        if doc['average']:
                            temp[w]['averages'].append(doc['average'])

                        temp[w]['counts']['multiClass'][
                            'c' + str(self.getClassNum(doc['average'], self.scoreRange))] += 1
                        maxClass = self.argmax(doc)
                        if maxClass == 'positive':
                            temp[w]['counts']['biClass']['c1'] += 1
                        elif maxClass == 'negative':
                            temp[w]['counts']['biClass']['c0'] += 1
                        else:
                            raise Exception('Max class should have been one of positive or negative')

                    else:
                        classNumber = self.getClassNum(doc['average'], self.scoreRange)
                        maxClass = self.argmax(doc)
                        temp[w] = {
                            '_id': w,

                            # For debug
                            'positives': [doc['positive']] if doc['positive'] else [],
                            'negatives': [doc['negative']] if doc['negative'] else [],
                            'averages': [doc['average']] if doc['average'] else [],
                            'counts': {'biClass': {
                                'c0': (1 if maxClass == 'negative' else 0) + self.laplaceSmoothening,
                                'c1': (1 if maxClass == 'positive' else 0) + self.laplaceSmoothening
                            }, 'multiClass': {}
                            }
                        }

                        for n in range(self.numClasses):
                            # starts with 1 because laplace smoothening
                            temp[w]['counts']['multiClass']['c' + str(n)] = \
                                (1 if n == classNumber else 0) + self.laplaceSmoothening

        self.targetCol.insert_many(wItemValue for wItemKey, wItemValue in temp.items())


class AssignLikelihood(object):
    def __init__(self, client_url, sourceDatabaseStr, sourceCollectionStr, targetDatabaseStr, targetCollectionStr):
        self.client = pymongo.MongoClient(client_url)
        self.sourceDatabaseStr = sourceDatabaseStr
        self.sourceCol = self.client[sourceDatabaseStr][sourceCollectionStr]
        self.targetCol = self.client[targetDatabaseStr][targetCollectionStr]
        self.nMultiClasses = NUM_CLASSES

    @staticmethod
    def getPosNegScore(ratios):
        nClasses = len(ratios)

        expectedClass = sum([ratios[i] * i for i in range(nClasses)])

        # pos is the tendency of the expected class to be towards the highest value. Ranges from 0 to 1
        pos = expectedClass / (nClasses - 1)
        neg = 1 - pos

        # A score between -1 to 1 where -1 is the most negative and +1 is the most positive
        score = pos - neg

        return pos, neg, score

    def getClassStats(self, classes: list, doc, aggregate):
        ret = {'counts': {}, 'probabilities': {}, 'ratios': {}}

        wordCount = sum([doc['c' + str(i)] for i in classes])
        totalWords = sum([aggregate['sum_c{0}'.format(i)] for i in classes])
        ret['probabilities']['word'] = wordCount / totalWords
        ret['counts']['total'] = wordCount
        ret['counts']['total_log10'] = math.log10(wordCount)
        for i in classes:
            className = 'c' + str(i)
            count = doc[className]
            probs = {'word_given_class': count / aggregate['sum_{0}'.format(className)] if aggregate[
                'sum_{0}'.format(className)] else 0, 'class_given_word': count / wordCount,
                     'word_and_class': count / totalWords, 'class': aggregate['sum_{0}'.format(className)] / totalWords}

            ret['counts'][className] = count
            ret['probabilities'][className] = probs

        totalWordGivenClass = sum([ret['probabilities']['c' + str(i)]['word_given_class'] for i in classes])

        # Calculate probability distribution of each class
        ratios = [ret['probabilities']['c' + str(i)]['word_given_class'] / totalWordGivenClass for i in classes]
        for i in range(len(classes)):
            ret['ratios']['c' + str(i)] = ratios[i]

        pos, neg, score = self.getPosNegScore(ratios)

        ret['positive'] = pos
        ret['negative'] = neg
        ret['score'] = score

        return ret

    def run(self):

        # BiClass : Classification into just positive and negative classes
        # Here 0 represents negative and 1 represents positive
        groupSums = {'_id': False, 'vocab_count': {'$sum': 1}, 'sum_c1': {'$sum': '$counts.biClass.c1'},
                     'sum_c0': {'$sum': '$counts.biClass.c0'}, }

        pipeline = [{'$group': groupSums}]

        aggBiClass = self.sourceCol.aggregate(pipeline=pipeline)
        aggBiClass = aggBiClass.next()

        # MultiClasses : Classification into specified number of classes

        groupSums = {'_id': False, 'vocab_count': {'$sum': 1}}

        # Get Sum of counts in each class
        for i in range(self.nMultiClasses):
            groupSums['sum_c{0}'.format(i)] = {'$sum': '$counts.multiClass.c{0}'.format(i)}

        pipeline = [{'$group': groupSums}]

        aggMulti = self.sourceCol.aggregate(pipeline=pipeline)
        aggMulti = aggMulti.next()

        temp = []  # for bulk write

        for doc in self.sourceCol.find():
            if doc['averages']:
                multiClassStats = self.getClassStats([i for i in range(self.nMultiClasses)],
                                                     doc['counts']['multiClass'], aggMulti)
                biClassStats = self.getClassStats([0, 1], doc['counts']['biClass'], aggBiClass)

                # Stats related to weighted average
                mean = np.mean(doc['averages'])
                median = np.median(doc['averages'])
                std = np.std(doc['averages'])
                if not std:
                    std = SMALL_NUMBER

                skewness = 3 * (mean - median) / std
                rng = np.ptp(doc['averages'], axis=0)

                stats = {'mean': mean, 'std': std, 'median': median, 'skewness': skewness, 'range': rng}

                temp.append({'_id': doc['_id'], 'multi': multiClassStats, 'biClass': biClassStats, 'stats': stats})

        self.targetCol.insert_many(temp, ordered=False,
                                   bypass_document_validation=True)


class BuildLexicon(object):
    def __init__(self, client_url, sourceDatabaseStr, sourceCollectionStr, targetDatabaseStr, targetCollectionStr):
        self.client = pymongo.MongoClient(client_url)
        self.sourceDatabaseStr = sourceDatabaseStr
        self.sourceCol = self.client[sourceDatabaseStr][sourceCollectionStr]
        self.targetCol = self.client[targetDatabaseStr][targetCollectionStr]

    def tukeysFences(self):
        totalDocs = self.sourceCol.count()

        q1Position = int(math.floor(totalDocs / 4))
        q3Position = int(math.floor(totalDocs * 3 / 4))

        q1Doc = next(self.sourceCol.find().sort('count.total', 1).skip(q1Position).limit(1))
        q3Doc = next(self.sourceCol.find().sort('count.total', 1).skip(q3Position).limit(1))

        iqr = q3Doc['count']['log10_total'] - q1Doc['count']['log10_total']

        # Tukey's fences
        k = 1.5
        lower = q1Doc['count']['log10_total'] - k * iqr
        upper = q3Doc['count']['log10_total'] + k * iqr

        self.targetCol.insert_many(
            doc for doc in self.sourceCol.find({'count.log10_total': {'$gt': lower, '$lt': upper}}))

    def run(self):
        """
            db.likelihood_19.aggregate([{'$group': {
            '_id': 0,
            'totalCount': {'$sum': '$count.total'},
            'totalWords':{'$sum':1},
            'avg':{'$avg':'$count.total'},
            'stdDev':{'$stdDevPop': '$count.total'}
        }}])
        :return:
        """

        pipeline = [{'$group': {
            '_id': False,
            'totalCount': {'$sum': '$multi.counts.total'},
            'totalWords': {'$sum': 1},
            'avgCount': {'$avg': '$multi.counts.total'},
            'avgStd': {'$avg': '$stats.std'},
            'avgAbsSkew': {'$avg': {'$abs': '$stats.skewness'}}
        }}]

        aggregated = self.sourceCol.aggregate(pipeline=pipeline)
        aggregated = aggregated.next()

        # select skewness outside this
        skewnessLimits = (-1 * aggregated['avgAbsSkew'] / 8, 1 * aggregated['avgAbsSkew'] / 8)

        # select scores outside this
        scoreLimits = (-4 / 8, +4 / 8)

        # select count higher than this
        minimumCount = aggregated['avgCount'] * 1 / 4

        # select standard deviation lower than this
        # Note that it was seen that stdev filter is useless
        # 100000 is making sure that maxStd is sufficiently large and does not filter results
        maxStd = aggregated['avgStd'] * 100000

        # select ranges higher than this
        minRange = 0.05

        # Turn off filters
        # skewnessLimits=(0,0)
        # scoreLimits=(0,0)
        # minimumCount=0
        # maxStd=9999999
        # minRange=0

        # print({
        #     'stats.range': {'$gte': minRange},
        #     '$and': [{'$or': [{'stats.skewness': {'$lte': skewnessLimits[0]}},
        #                       {'stats.skewness': {'$gte': skewnessLimits[1]}}]},
        #              {'$or': [{'multi.score': {'$lte': scoreLimits[0]}},
        #                       {'multi.score': {'$gte': scoreLimits[1]}}]}],
        #     'multi.counts.total': {'$gte': minimumCount},
        #     'stats.std': {'$lte': maxStd}
        #
        # })

        self.targetCol.insert_many(
            {'_id': doc['_id'], 'positive': doc['multi']['positive'], 'negative': doc['multi']['negative'],
             'score': doc['multi']['score'], 'pdf': doc['multi']['ratios'], 'stats': doc['stats']} for doc in

            self.sourceCol.find({
                'stats.range': {'$gte': minRange},
                '$and': [{'$or': [{'stats.skewness': {'$lte': skewnessLimits[0]}},
                                  {'stats.skewness': {'$gte': skewnessLimits[1]}}]},
                         {'$or': [{'multi.score': {'$lte': scoreLimits[0]}},
                                  {'multi.score': {'$gte': scoreLimits[1]}}]}],
                'multi.counts.total': {'$gte': minimumCount},
                'stats.std': {'$lte': maxStd}
            })
            # self.sourceCol.find()
        )
