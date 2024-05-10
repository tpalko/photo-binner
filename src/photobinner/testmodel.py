#!/usr/bin/env python3

import sys 

import simplejson as json 
import cowpy 

logger = cowpy.getLogger()

from frank.database.database import Database, DatabaseConfig
from frank.database.model import JsonColumn, BaseModel, Column, JsonColumn

from pbdb import Session, Target, Source, Image, Encounter


init = {
    'parameters_json': '{"thing":"test"}'    
}
print(f'init: {init}')
s = Session(**init) 

print(f'client user col names: {s._meta.user_def_col_names}')
print(f's: {s}')
print(f'parameters_json: {s.parameters_json}')

print('saving')
s.save()

# print(f'saved: s.id={s.id}')

# sessions = Session.get(db, parameters_json=s.parameters_json)

# print(f'found {len(sessions)} sessions')

# if len(sessions) > 0:

#     last_session = sessions[-1]

#     print(f'here is one: (created_at: {last_session.created_at}, id: {last_session.id}) {last_session}')
    
#     print(f're-fetching {last_session.id}')

#     fetched_last_session = Session.first(db, id=last_session.id)

#     print(fetched_last_session)
#     if fetched_last_session:
#         print(fetched_last_session.parameters_json)
#         print(fetched_last_session.parameters_json['thing'])
#         fetched_last_session.parameters_json['thing'] = 'never!'
#         print(fetched_last_session.parameters_json['thing'])
#         fetched_last_session.save(db)

# new_s = Session(**init)
# new_s.parameters_json['thing'] = 'not testing'
# new_s.upsert(db, parameters_json=init)