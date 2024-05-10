import cowpy
import simplejson as json
from enum import Enum 
from frank.database.model import JsonColumn, StringColumn, IntColumn, BaseModel
from frank.database.database import Database, DatabaseConfig

logger = cowpy.getLogger()

class EncounterStatus(Enum):
    COMPLETE = 1

DBCONFIG = {    
    'base': {
        'primary_key': 'id',
        'timestamps': ['created_at', 'updated_at']
    },    
    'models': {
        'sessions': [
            { 'name': 'parameters_json', 'type': json }
        ],
        'sources': [
            { 'name': 'name', 'type': str }
        ],
        'targets': [
            { 'name': 'name', 'type': str }
        ],
        'images': [
            { 'name': 'original_source_id', 'type': int },
            { 'name': 'original_filepath', 'type': str },
            { 'name': 'size_kb', 'type': int },             
            { 'name': 'md5', 'type': str, 'size': 32 }            
        ],
        'encounters': [
            { 'name': 'session_id', 'type': int },
            { 'name': 'image_id', 'type': int },
            { 'name': 'source_id', 'type': int },
            { 'name': 'source_filepath', 'type': str },            
            { 'name': 'target_id', 'type': int },
            { 'name': 'target_filepath', 'type': str },
            { 'name': 'status', 'type': str },
        ],
    },
    'foreign_keys': {
        'images': {
            'sources': 'id'
        },
        'encounters': {
            'sessions': 'id',
            'images': 'id',
            'sources': 'id',
            'targets': 'id'
        }
    }
}

class Session(BaseModel):
    parameters_json = JsonColumn()

class Source(BaseModel):
    name = StringColumn()

class Target(BaseModel):
    name = StringColumn()

class Image(BaseModel):
    original_source_id = IntColumn()
    original_filepath = StringColumn()
    size_kb = IntColumn()
    md5 = StringColumn()

class Encounter(BaseModel):
    session_id = IntColumn()
    image_id = IntColumn()
    source_id = IntColumn()
    source_filepath = StringColumn()
    target_id = IntColumn()
    target_filepath = StringColumn()
    status = StringColumn()


dbConfig = {
    'host': 'localhost',
    'user': 'photobinner',
    'password': 'photobinner',
    'name': 'photobinner' 
}

Database.createInstance(
    config=DatabaseConfig.NewMariadb(**dbConfig),
    models = [Session, Target, Source, Image, Encounter]
)
