import re
import logging 
import glob
import os
import json

logger = logging.getLogger(__name__)

class PhotoStats(object):

    sessionfile = None 
    
    def __init__(self, *args, **kwargs):
        self.operator_uid = 1000
        if 'operator_uid' in kwargs:
            self.operator_uid = kwargs['operator_uid']
    
    def _init_run_stats(self, dry_run):
        
        self.run_stats = {
            'meta': {
                'runs': [],
                'status': 'open',
                'dry_run': dry_run
            },
            'processed_files': {},
            'moves': {},
            'correct': {},
            'date_sources': {},
            'anomalies': {}
        }
        
    def _get_json_content(self, filepath):
        j = None
        with open(filepath, 'r') as o:
            filepath_contents = o.read()
            try:
                j = json.loads(filepath_contents)
            except:
                logger.warning(" - failed to load %s as JSON" % filepath)
        return j
    
    def write_out(self):
        # -- thinking one file should be kept in perpetuity..
        #if not self.sigint and not 'exception' in run_stat:
        #    self.run_stats['meta']['status'] = 'closed'
        logger.info("Processing session and writing out..")
        updated_session = json.dumps(self.run_stats, indent=4, sort_keys=True)

        if self.sessionfile:
            with open(self.sessionfile, 'w') as f:
                f.write(updated_session)

            os.chown(self.sessionfile, self.operator_uid, -1)
            #pprint.pprint(self.run_stats, indent=4)

            logger.info("Session %s end" % self.sessionfile)
        else:
            print(updated_session)
            
    def get_open_session_files(self, stats_folder, dry_run):
        open_sessions = []
        for outfile in [ g for g in glob.glob(os.path.join(stats_folder, "*")) if re.search("photobinner\_[0-9]{8}\_[0-9]{6}%s\_[A-Za-z0-9]+\.out$" % ('_dry_run' if dry_run else ''), g) ]:
            j = self._get_json_content(outfile)
            if j and 'meta' in j and 'status' in j['meta'] and j['meta']['status'] == 'open':
                open_sessions.append(outfile)
        return open_sessions
        
    def load_session(self, stats_folder, dry_run=False):
        logger.info("Gathering open sessions..")
        open_sessions = self.get_open_session_files(stats_folder, dry_run)

        # -- TODO: menu to choose a session
        session_choice = None
        if len(open_sessions) > 0:
            logger.warning("Please choose a session:")
        else:
            logger.warning("Please choose:")
        while not (session_choice and (session_choice.lower() in ['n','s','q'] or (session_choice.isdigit() and int(session_choice)-1 in range(len(open_sessions))))):
            for s in range(len(open_sessions)):
                print(("(%s) %s" % ((s+1), open_sessions[s])))
            print("(n)ew session")
            print("(s)kip session")
            print("(q)uit")
            print("? ")
            session_choice = input()

        if session_choice.isdigit():
            self.sessionfile = open_sessions[int(session_choice)-1]
            logger.warn("Continuing session file: %s" % self.sessionfile)
            self.run_stats = self._get_json_content(self.sessionfile)
            self.run_stats['meta']['dry_run'] = self.run_stats['meta']['dry_run'] == 'true'
            if self.run_stats['meta']['dry_run'] != dry_run:
                logger.warn("The selected session is%s a dry run, however the program was called with%s the dry run flag. Forcing the flag to match the file." % (' not' if not self.run_stats['meta']['dry_run'] else '', 'out' if not dry_run else ''))
                dry_run = self.run_stats['meta']['dry_run'] == 'true'
        elif session_choice.lower() == 's':
            self.run_stats['meta']['dry_run'] = 'true' if dry_run else 'false'
            logger.warn("Skipping session tracking")
        elif session_choice.lower() == 'n':
            good_name = None
            while(not good_name):
                print("Enter a name for the new session (numbers and letters only please):")
                session_name = input()
                if len([ t for t in session_name.split(' ') if not t.isalnum() ]) == 0:
                    good_name = session_name.replace(' ', '').lower()
            timestamp = datetime.strftime(datetime.now(), "%Y%m%d_%H%M%S")
            outfile_name = "photobinner_%s%s%s.out" % (timestamp, ('_dry_run' if dry_run else ''), "_%s" % good_name if good_name else "_unnamed")
            self.sessionfile = os.path.join(stats_folder, outfile_name)
            logger.warn("Starting a new session file: %s" % self.sessionfile)
            
            if not os.path.exists(stats_folder):
                logger.info("Creating out folder: %s" % stats_folder)
                os.makedirs(stats_folder)
                os.chown(stats_folder, self.operator_uid, -1)
            else:
                logger.info("Out folder found: %s" % stats_folder)
                
            self._init_run_stats(dry_run)
            self.run_stats['meta']['dry_run'] = 'true' if dry_run else 'false'
            with open(self.sessionfile, 'w') as s:
                s.write(json.dumps(self.run_stats))
        else: # session_choice.lower() == 'q':
            exit(0)
    
    def get_session_processed_files(self):
        return self.run_stats['processed_files']
    
    def set_session_processed_files(self, source_name, processed_files):
        self.run_stats['processed_files'][source_name] = processed_files
    
    def push_run_stat(self, type, key, value):
        if key not in self.run_stats[type]:
            self.run_stats[type][key] = []
        self.run_stats[type][key].append(value)

    def append_run_stat(self, run_stat):
        self.run_stats['meta']['runs'].append(run_stat)
                
    def increment_run_stat(self, cat, current_folder, target_folder=None):
        if cat not in self.run_stats:
            self.run_stats[cat] = {}
        if current_folder not in self.run_stats[cat]:
            if target_folder:
                self.run_stats[cat][current_folder] = {}
            else:
                self.run_stats[cat][current_folder] = 0
        if target_folder and target_folder not in self.run_stats[cat][current_folder]:
            self.run_stats[cat][current_folder][target_folder] = 0

        if target_folder:
            self.run_stats[cat][current_folder][target_folder] += 1
        else:
            self.run_stats[cat][current_folder] += 1

        # base = self.run_stats[cat]
        # for k in kwargs:
        #     if kwargs[k] not in base:
        #         base[kwargs[k]] = {}
        #     base = base[kwargs[k]]
        # if type(base).__name__ == 'dict':
        #     base = 0
        # base = base + 1
