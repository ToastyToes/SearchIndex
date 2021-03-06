import boto3
from datetime import datetime
from boto3.dynamodb.conditions import Key, Attr
from stopword_model import StopWordModel


class StopWordController(object):

    STOP_WORD_TABLE = 'STOP_WORD'

    def __init__(self):
        self._dynamodb = boto3.client('dynamodb')
        self._stop_word_table = (boto3.resource('dynamodb')
                                .Table(self.STOP_WORD_TABLE))

    # retrieves the stop
    def get_word(self, word):
        try:
            res = self._stop_word_table.query(
                KeyConditionExpression=Key(StopWordModel.PKEY).eq(word)
            )
            if res['Count'] == 0:
                return None

            sw = StopWordModel()
            return sw.load_from_input(res['Items'][0])

        except Exception as ex:
            print "ERROR: Failed to query {0} \
            table: {1}".format(self.STOP_WORD_TABLE, ex)
            return None

    # create a new index document if the provided model is valid and verified
    def add_word(self, stop_word_model):
        try:
            # replacing since update_item cannot modify sortkey
            if(not stop_word_model.verify()):
                return

            self._stop_word_table.put_item(
                Item=stop_word_model.get_payload()
            )
            return True
        except Exception as ex:
            print "ERROR: Failed to insert into STOP_WORD: {0}".format(ex)
            return False
