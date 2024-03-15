from datetime import datetime 
from frank.database import Database, DatabaseConfig
import simplejson as json

DBCONFIG = {    
    'base': {
        'primary_key': 'id',
        'timestamps': ['created_at', 'updated_at']
    },    
    'models': {
        'images': [
            { 'name': 'original_source_id', 'type': int },
            { 'name': 'original_filepath', 'type': str, 'size': 255 },
            { 'name': 'size_kb', 'type': int },             
            { 'name': 'md5', 'type': str, 'size': 32 }            
        ],
        'sources': [
            { 'name': 'name', 'type': str }
        ],
        'sessions': [
            { 'name': 'parameters_json', 'type': json }
        ],
        'encounters': [
            { 'name': 'session_id', 'type': int },
            { 'name': 'source_id', 'type': int },
            { 'name': 'image_id', 'type': int },             
            { 'name': 'result', 'type': str },
            { 'name': 'destination_filepath', 'type': float },             
        ],
    },
    'foreign_keys': {
        'images': {
            'sources': 'id'
        },
        'encounters': {
            'sessions': 'id',
            'sources': 'id',
            'images': 'id'
        }
    }
}

class PbDb(object):
    
    db = None 

    def __init__(self, *args, **kwargs):

        self.db = Database(
            config=DatabaseConfig.NewMariadb(**kwargs),
            tables=DBCONFIG
        )
