import pymongo
from bson.code import Code
from bson.son import SON

MAX_WORD_LENGTH = 200


class WordCount(object):
    def __init__(self, client_url, sourceDatabaseStr, sourceCollectionStr, targetDatabaseStr, targetCollectionStr):
        self.client = pymongo.MongoClient(client_url)
        self.sourceDatabase = sourceDatabaseStr
        self.sourceCol = self.client[sourceDatabaseStr][sourceCollectionStr]
        self.targetDatabaseStr = targetDatabaseStr
        self.targetCollectionStrTemp = targetCollectionStr + "_temp"

        self.targetFinal = targetCollectionStr

    def run(self):
        mapScript = Code('''
            function() {
                var summary = this.words;
                var countSummary = this.counts;
                var total = this.total;
                   for (var i = summary.length - 1; i >= 0; i--) {
                              key=summary[i];
                              
                              value={
                                  'documents':1,
                                  'occurrences':countSummary[key],
                                  'totalWords':total
                              };
                            
                            key=key.substring(0,Math.min(''' + str(MAX_WORD_LENGTH) + ''',key.length));
                            
                            emit(key, value);
                     }
            };''')

        reduceScript = Code('''
            function( key, values ) {
                var ret = {'documents':0,'occurrences':0,'totalWords':0}
                
                if (Array.isArray(values)){
                    values.forEach(function(v) {
                        ret['documents']+=v['documents'];
                        ret['occurrences']+=v['occurrences'];
                        ret['totalWords']+=v['totalWords'];
                    });
                } else {
                        ret['documents']+=values['documents'];
                        ret['occurrences']+=values['occurrences'];
                        ret['totalWords']+=values['totalWords'];
                }
                

                return ret;
            };
            ''')

        self.sourceCol.map_reduce(mapScript, reduceScript, out=SON(
            [('replace', self.targetCollectionStrTemp), ("db", self.targetDatabaseStr)]))

        totalDocs = self.sourceCol.count() * 1.0
        tempCol = self.client[self.sourceDatabase][self.targetCollectionStrTemp]

        pipeline = [
            {'$project': {
                'documents': '$value.documents',
                'occurrences': '$value.occurrences',
                'totalWords': '$value.totalWords',
                'TF': {'$add': [1, {'$log10': '$value.occurrences'}]},
                'IDF': {'$log10': {'$divide': [totalDocs, '$value.documents']}}
            }},
            {'$project': {
                'documents': 1,  # means to include. Not setting to 1
                'occurrences': 1,
                'totalWords': 1,
                'TF': 1,
                'IDF': 1,
                'TF_IDF': {'$multiply': ['$TF', '$IDF']}
            }},
            {
                '$sort': {'TF_IDF': -1}},
            {'$out': self.targetFinal}
        ]

        tempCol.aggregate(pipeline, allowDiskUse=True)
