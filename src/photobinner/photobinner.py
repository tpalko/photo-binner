#!/usr/bin/env python3

import os
import sys
import signal
from datetime import datetime, timedelta
import click
import logging
import re
import shutil
import pprint
import json
#import importlib
import glob
from configparser import ConfigParser
from pwd import getpwnam
import traceback
#from grp import getgrnam
# print(sys.path)
from plugin.source import StitchFolder, SourceFile
from utils.dates import get_target_date
from utils.stats import PhotoStats
from utils.pathing import calculate_target_folder
from utils.common import hash_equal

'''
If debug, show file heading and any indented debug lines for all files
If info, show file heading and any indented info lines for all files
> info, show file heading and any enabled lines only for files needing changes
If a warn or critical log will be printed, show file heading for that file

There are several debug or info logs that occur prior to knowing whether or not
a file needs to be changed. Therefore, the heading line cannot be a simple log
at the beginning of the loop - it is shown not based on log level but based on
future knowledge.
'''

logger = logging.getLogger(__name__)

config = ConfigParser()
pb_config = os.path.expanduser('~/.pbrc')
user_config = None 
STATS_FOLDER = "pb_stats"
if os.path.isfile(pb_config):
    user_config = pb_config 
    logger.info("You know, if ~/.pbrc is a folder, photobinner will store run stats there instead of here")
elif os.path.isdir(pb_config) and os.path.isfile(os.path.join(pb_config, 'config')):
    user_config = os.path.join(pb_config, 'config')
    STATS_FOLDER = os.path.join(pb_config, 'stats')
    if not os.path.exists(STATS_FOLDER):
        os.makedirs(STATS_FOLDER)
if user_config:
    logger.debug("Reading %s" % user_config)
    config.read(user_config)
else:
    logger.debug("No config, using baked-in defaults..")

DEFAULT_TRANSFER_METHOD = 'copy'
DEFAULT_TARGET = config.defaults()['target']
DEFAULT_MASK = "*"
EXACT_MATCHES_FOLDER = config.get('folders', 'exact_matches')
COPY_EXACT_MATCHES = config.getboolean('folders', 'copy_exact_matches')
STITCH_FILE_MATCH = "^ST[A-Z]_[0-9]+.JPG$"

OWNER_UID = os.getuid()
if 'owner' in config.defaults():
    OWNER_UID = getpwnam(config.defaults()['owner'])[2]
#GROUP = getgrnam(config.defaults()['group'] or os.getgid())[2]

# INBOX_PATHS = [
#     '/media/storage/pics/mobile_inbox',
#     '/media/storage/pics/inbox'
# ]

class PhotoBinner(object):

    dry_run = False
    preserve_folders = 0
    exclude_descriptive = ''
    filing_preference = 'date'
    target_base_folder = ''
    mask = DEFAULT_MASK
    from_date = None
    exact_matches_folder = "./exact_matches"
    user_source = None
    sigint = False
    transfer_method = DEFAULT_TRANSFER_METHOD
    stats = None 

    def __init__(self, *args, **kwargs):
        for k in kwargs:
            logger.debug("Setting %s -> %s" % (k, kwargs[k]))
            self.__setattr__(k, kwargs[k])
        for v in [ v for v in dir(self) if v.find("_") != 0 ]:
            t = type(self.__getattribute__(v))
            if t in [str, int, bool, str] or not t:
                logger.debug("%s: %s" % (v, self.__getattribute__(v)))
        self.stats = PhotoStats(operator_uid=OWNER_UID)
        self._initialize()

    def move(self, src, dest, time_tuple=None):
        shutil.move(src, dest)
        if time_tuple:
            os.utime(dest, (time_tuple[0], time_tuple[1]))
        os.chown(dest, OWNER_UID, -1)

    def copy(self, src, dest, time_tuple=None):
        shutil.copy2(src, dest)
        os.chown(dest, OWNER_UID, -1)

    '''
    T:  Bus=02 Lev=01 Prnt=01 Port=01 Cnt=01 Dev#=  2 Spd=480 MxCh= 0
    D:  Ver= 2.00 Cls=00(>ifc ) Sub=00 Prot=00 MxPS=64 #Cfgs=  1
    P:  Vendor=058f ProdID=6362 Rev=01.00
    S:  Manufacturer=Generic
    S:  Product=Mass Storage Device
    S:  SerialNumber=058F63626376
    C:  #Ifs= 1 Cfg#= 1 Atr=80 MxPwr=100mA
    I:  If#= 0 Alt= 0 #EPs= 2 Cls=08(stor.) Sub=06 Prot=50 Driver=usb-storage

    NAME   SERIAL       UUID                                 PARTUUID LABEL       PARTLABEL
    sde    058F63626376
      sde1              0782-073F                                     EOS_DIGITAL
    '''

    def _determine_move_action(self, sourcefile, target_folder, filename):
        '''
        Compare initial and target paths, notice and compare any existing files, determine final target and if move/copy action should be taken.
        '''

        move_necessary = False
        move_action = "not determined"
        new_path = os.path.join(target_folder, filename)

        if sourcefile.original_path == new_path:
            move_action = " - current path is correct, matches calculated target, not moving"
        elif os.path.exists(new_path):
            logger.warn(" - another file exists at destination path, comparing files..")
            if hash_equal(sourcefile.working_path, new_path):
                move_necessary = COPY_EXACT_MATCHES
                if move_necessary:
                    logger.warn(" - file at destination path is exact, moving to %s" % self.exact_matches_folder)
                    target_folder = self.exact_matches_folder
                    new_path = os.path.join(target_folder, filename)
                    move_action = "exact match at target, moving to %s" % target_folder
                else:
                    logger.warn(" - file at destination path is exact, not moving")
                self.stats.push_run_stat('anomalies', 'content-match-at-target', sourcefile.original_path)
            else:
                logger.warn(" - file at destination path is different, we have a duplicate-in-name-only")
                move_necessary = True
                dupe_count = 0
                dupe_folder = target_folder
                # - calculate dupe path if filename already exists
                while os.path.exists(new_path):
                    dupe_folder = os.path.join(target_folder, "dupe", str(dupe_count))
                    new_path = os.path.join(dupe_folder, filename)
                    move_action = "filename match, modifying new path -> %s" % new_path
                    # -- if, while creating an appropriate dupe folder we encounter an identical file, stop processing 
                    if os.path.exists(new_path) and sourcefile.original_path == new_path and hash_equal(sourcefile.working_path, new_path):
                        move_action = " - this file already exists as a duplicate, not moving"
                        move_necessary = False
                        break
                    dupe_count = dupe_count + 1
                target_folder = dupe_folder
                self.stats.push_run_stat('anomalies', 'filename-match-at-target', sourcefile.original_path)
        else:
            move_action = "normal move %s -> %s" % (sourcefile.original_path, new_path)
            move_necessary = True

        logger.info(" - %s" % move_action)

        return target_folder if move_necessary else None

    def _process_stitch_folder(self, source, stitch_folder):
        logger.info("Processing stitch folder: %s" % stitch_folder.working_path)
        for stitch_file in [ g for g in glob.glob("%s/*" % stitch_folder.working_path) if re.search(STITCH_FILE_MATCH, g.rpartition('/')[-1]) ]:
            logger.info(" - found stich file: %s" % stitch_file)
            stitch_file_source_file = SourceFile(stitch_file)
            (target_date, target_atime, target_mtime, new_filename, target_date_assigned_from,) = get_target_date(stitch_file_source_file, self.stats.push_run_stat)
            if not target_date:
                logger.warn(" - no target date could be calculated")
                raise Exception("no target date could be calculated")
            stitch_folder_name = stitch_folder.working_path.rpartition('/')[-1]
            source.exclude_descriptive.append(stitch_folder_name)
            target_folder = calculate_target_folder(source, stitch_file_source_file, target_date, self.filing_preference, self.preserve_folders)
            target_folder = self._determine_move_action(stitch_folder, target_folder, stitch_folder_name)
            if target_folder:
                new_path = os.path.join(target_folder, stitch_folder_name)
                if self.dry_run:
                    logger.info(" - dry run, no action")
                else:
                    logger.info(" - moving %s -> %s" % (stitch_folder.working_path, new_path))
                    source.transfer_method(stitch_folder.working_path, new_path)

    def _process_file(self, source, sourcefile):

        current_path_parts = sourcefile.original_path.rpartition('/')
        current_folder = current_path_parts[0]
        filename = current_path_parts[-1]

        # - if DEBUG or INFO, logs immediately, otherwise requires a file change
        # - implies that outside the file change block, logs must be < WARN
        logger.info("Processing %s.." % sourcefile.original_path)

        (target_date, target_atime, target_mtime, new_filename, target_date_assigned_from,) = get_target_date(sourcefile.working_path, sourcefile.original_path, self.stats.push_run_stat)

        if not target_date:
            logger.warn(" - no target date could be calculated")
            raise Exception("no target date could be calculated")

        if new_filename:
            filename = new_filename

        target_folder = calculate_target_folder(source, sourcefile, target_date, self.filing_preference, self.preserve_folders)
        target_folder = self._determine_move_action(sourcefile, target_folder, filename)

        if target_folder:
            
            new_path = os.path.join(target_folder, filename)
            self.stats.increment_run_stat('moves', current_folder=current_folder, target_folder=target_folder)

            if self.dry_run:
                logger.info(" - dry run, no action")
            else:
                # - actually move the file and fix timestamps
                # - create final path
                if not os.path.isdir(target_folder):
                    os.makedirs(target_folder)
                    os.chown(target_folder, OWNER_UID, -1)

                file_stats = os.stat(sourcefile.working_path)
                logger.info(" - %s MB" % str(int(file_stats.st_size)/(1024*1024)))
                source.transfer_method(sourcefile.working_path, new_path, (target_atime, target_mtime,))
                
                # - calculate various companion filenames
                variants = [
                    "%s.xmp" % filename,
                    "._%s" % filename,
                    re.sub(r'\.CRW$', ".THM", filename) if filename[-4:] == ".CRW" else None,
                    re.sub(r'\.AVI$', ".THM", filename) if filename[-4:] == ".AVI" else None
                ]

                for variant in [ { 'name': v, 'path': os.path.join(current_folder, v) } for v in variants if v ]:
                    if not os.path.exists(variant['path']):
                        continue
                    logger.info(" - processing existing variant %s" % variant['name'])
                    new_variant_filepath = os.path.join(target_folder, variant['name'])
                    logger.info("   - %s -> %s" % (variant['path'], new_variant_filepath))
                    source.transfer_method(variant['path'], new_variant_filepath)

        else:
            self.stats.increment_run_stat('correct', current_folder=current_folder)
        
    '''
    Initialization Block
    '''

    source_types = {}
    verified_sources = {}
    attempt_sources = {}
    aux_sources = {}

    def _verify_chosen_sources(self):
        for s in self.attempt_sources:
            logger.info("Verifying source: %s" % s)
            if self.attempt_sources[s].verify():
                logger.info(" - verified!")
                self.verified_sources[s] = self.attempt_sources[s]
            else:
                logger.info(" - not verified!")

        logger.info("%s/%s sources verified: [%s]" % (len(list(self.verified_sources.keys())), len(list(self.attempt_sources.keys())), ",".join([ s for s in list(self.verified_sources.keys()) ])))

    def _identify_chosen_sources(self):
        # -- select chosen source types
        if self.user_source:
            if self.user_source in list(self.aux_sources.keys()):
                self.attempt_sources[self.user_source] = self.aux_sources[self.user_source]
            else:
                # -- if self.user_source doesn't match a preconfigured source
                # -- interpret it as a path on-disk
                mountpoint = os.path.abspath(self.user_source)
                source_folder = self.source_types['Folder'](
                    type='Folder',
                    mountpoint=mountpoint,
                    transfer_method=self.move if self.transfer_method == 'move' else self.copy,
                    exclude_descriptive=self.exclude_descriptive.split(','),
                    target=self.target_base_folder
                )
                self.attempt_sources[mountpoint] = source_folder
        else:
            for s in list(self.aux_sources.keys()):
                self.attempt_sources[s] = self.aux_sources[s]

        logger.info("%s/%s sources selected: [%s]" % (len(list(self.attempt_sources.keys())), len(list(self.aux_sources.keys())), ",".join([ "%s (%s)" % (s, self.attempt_sources[s].type) for s in list(self.attempt_sources.keys()) ])))

    def _load_configured_sources(self):

        logger.debug("Finding sources..")

        if self.mask != DEFAULT_MASK:
            logger.warn("Filtering all sources by '%s'" % self.mask)

        # -- load configured source types
        for section_name in [ s for s in config.sections() if s.startswith('Source-') ]:
            logger.debug(f'{section_name}..')
            source_config = dict(config.items(section_name))
            source_type = source_config['type']
            if source_type not in self.source_types:
                logger.warn("Configured source with type '%s' is not represented by a Source implementation" % source_type)
                continue
            if 'exclude_descriptive' in source_config:
                source_config['exclude_descriptive'] = source_config['exclude_descriptive'].split(',')
            source_name = section_name.rpartition('-')[-1]
            source_config['name'] = source_name
            # -- convert string value transfer method to function handle 
            # -- transfer method defaults to 'copy' unless stated 'move'
            source_config['transfer_method'] = self.move if 'transfer_method' in source_config and source_config['transfer_method'] == 'move' else self.copy
            # -- pulling in invocation-time parameters 
            source_config['mask'] = self.mask
            source_config['from_date'] = self.from_date
            if 'target' not in source_config:
                logger.debug(" - target not defined, setting: %s" % (self.target_base_folder))
                source_config['target'] = self.target_base_folder
            else:
                logger.debug(" - target defined: %s" % source_config['target'])
            
            # -- default instantiates a 'type' source with kwargs from the ini k/v
            self.aux_sources[source_name] = self.source_types[source_type](**source_config)

        logger.info("%s source configurations found: [%s]" % (len(list(self.aux_sources.keys())), ",".join([ s for s in list(self.aux_sources.keys()) ])))

    def _load_source_types(self):
        logger.debug("Loading source interfaces..")
        # from sources import android
        # self.source_types['Android'] = android.classdef()
        #mod = __import__("photobinner.sources")
        from sources import sources 
        for source_class in sources():
            logger.debug("Loading module: %s" % source_class)
            self.source_types[source_class().__class__.__name__] = source_class
            #Source.register(source_class)
        logger.info("%s source interfaces configured: [%s]" % (len(list(self.source_types.keys())), ",".join([ s for s in list(self.source_types.keys()) ])))

    def _initialize(self):

        signal.signal(signal.SIGINT, self.sigint_handler())

        self._load_source_types()
        self._load_configured_sources()
        self._identify_chosen_sources()
        self._verify_chosen_sources()

        if len(list(self.verified_sources.keys())) == 0:
            logger.debug("No provided source could be verified")
            exit(0)
        
        if not os.path.exists(self.exact_matches_folder):
            os.makedirs(self.exact_matches_folder)
            os.chown(self.exact_matches_folder, OWNER_UID, -1)

        self.stats.load_session(STATS_FOLDER, dry_run=self.dry_run)
        
        session_processed_files = self.stats.get_session_processed_files()
        
        # -- populated verified sources with processed files from previous runs
        for v in [ v for v in self.verified_sources if v in session_processed_files ]:
            self.verified_sources[v].processed_files = session_processed_files[v]
            logger.info("Source: %s -> Found %s processed files" % (v, len(self.verified_sources[v].processed_files)))

        # for g in glob.glob("bin/sources/*.py"):
        #     if g == "bin/sources/__init__.py":
        #         continue
        #     # module_name = g.replace("/", ".").rpartition(".")[0]
        #     # module = importlib.import_module(module_name)
        #     # source_class = module.classdef()
        #     module_name = g.replace("/", ".").rpartition(".")[0]
        #     source_class = importlib.import_module(module_name).classdef()
        #     source_name = source_class().__class__.__name__
        #     self.source_types[source_name] = source_class
        #     Source.register(source_class)

    '''
    End Initialization Block
    '''

    def sigint_handler(self, source_handler=None):
        def handler(sig, frame):
            self.sigint = True
            if source_handler:
                source_handler(sig, frame)
        return handler

    def run(self):

        for s in list(self.verified_sources.keys()):
            source = self.verified_sources[s]
            count = self.smoke_test if self.dry_run else -1
            signal.signal(signal.SIGINT, self.sigint_handler(source.sigint_handler()))
            if self.sigint:
                logger.fatal("Noticed sigint in main loop, breaking..")
                break
            run_stat = { 'source': s, 'start': datetime.strftime(datetime.now(), "%Y-%m-%dT%H:%M:%S"), 'file_count': 0 }
            try:
                if source.mountpoint and os.path.isfile(source.mountpoint):
                    logger.info("Processing single file %s " % source.mountpoint)
                    try:
                        sourcefile = SourceFile(source.mountpoint)
                        self._process_file(source=source, sourcefile=sourcefile)
                        run_stat['file_count'] += 1
                        self.stats.append_processed_file(s, sourcefile.original_path)
                        source.processed_files.append(source.mountpoint)
                    except:
                        logger.error("Exception caught processing file: %s" % source.mountpoint)
                        logger.error(str(sys.exc_info()[0]))
                        logger.error(str(sys.exc_info()[1]))
                        traceback.print_tb(sys.exc_info()[2])
                else:
                    logger.info("Processing paths from source..")
                    for sf in source.paths():
                        if self.sigint:
                            break
                        try:
                            if isinstance(sf, StitchFolder):
                                self._process_stitch_folder(source=source, stitch_folder=sf)
                            else:
                                if self.stats.is_source_file_processed(s, sf.original_path):
                                    logger.info(" - [%s] %s found as processed, skipping.." % (s, sf.original_path))
                                    continue 
                                self._process_file(source=source, sourcefile=sf)
                                run_stat['file_count'] += 1
                                self.stats.append_processed_file(s, sf.original_path)
                                source.processed_files.append(sf.original_path)
                                if count > 0:
                                    count -= 1
                                if count == 0:
                                    logger.info("Smoke test limit (%s) reached" % self.smoke_test)
                                    break
                        except:
                            logger.error("Exception caught processing file: %s (%s)" % (sf.working_path, sf.original_path))
                            logger.error(str(sys.exc_info()[0]))
                            logger.error(str(sys.exc_info()[1]))
                            traceback.print_tb(sys.exc_info()[2])
            except:
                run_stat['exception'] = str(sys.exc_info()[1])
                run_stat['stack_trace'] = str(traceback.extract_tb(sys.exc_info()[2]))
                logger.error(str(sys.exc_info()[0]))
                logger.error(str(sys.exc_info()[1]))
                traceback.print_tb(sys.exc_info()[2])

            logger.info("Closing the run..")
            run_stat['stop'] = datetime.strftime(datetime.now(), "%Y-%m-%dT%H:%M:%S")            
            self.stats.append_run_stat(run_stat)

        # logger.info("Capturing processed files from sources..")
        # for s in list(self.verified_sources.keys()):
        #     self.stats.set_session_processed_files(s, self.verified_sources[s].processed_files)            

        self.stats.write_out()

        logger.info("All operations complete.")

@click.command()
@click.option('--source', '-s', 'user_source', help='Source folder')
@click.option('--target', '-t', 'target', default=DEFAULT_TARGET, help='Target folder, default "%s"' % DEFAULT_TARGET)
@click.option('--mask', '-m', 'mask', default=DEFAULT_MASK, help='Filename mask, default %s' % DEFAULT_MASK)
@click.option('--from-date', '-f', 'from_date', type=click.DateTime(), default=None, help='(Android Only) Process files only newer than this date (YYYY-MM-DD), default empty')
@click.option('--preserve-folders', '-p', 'preserve_folders', default=0, help='Number of parent folders to preserve when extracting descriptive text')
@click.option('--exclude-descriptive', '-e', 'exclude_descriptive', default='', help='String matches to omit when parsing path tokens for descriptive text')
@click.option('--filing-preference', '-i', 'filing_preference', default='date', help='date: year/date_label, label: year/label/date')
@click.option('--dry-run', '-d', 'dry_run', is_flag=True, help='Only print what would happen. Make no filesystem changes.')
@click.option('--smoke-test', '-k', 'smoke_test', default=-1, help='Process only this number of records from each verified source as a test. Only active if --dry-run')
@click.option('--setup-only', '-o', 'setup_only', is_flag=True, help='Run everything up to the actual processing of files.')
@click.option('--loglevel', '-l', 'loglevel', default='info', help='Logging level (debug, info, warn, error, fatal)')
@click.option('--transfer-method', '-b', 'transfer_method', default=DEFAULT_TRANSFER_METHOD, help='Whether to \'move\' or \'copy\' files')
def main(user_source, target, mask, from_date, preserve_folders, exclude_descriptive, filing_preference, dry_run, smoke_test, setup_only, loglevel, transfer_method):

    # use cases:
    #     - import images from mounted SD card/USB stick/mobile device
    #         $ ./pic_date_sorter.py -i
    #     - sort images in place
    #     - sort images from one location to another
    # these can be combined into a single operation: grab files from somewhere and sort them either in-place or to another location
    #     source defaults to searching for a mounted device but can be overwritten
    #     target defaults to DEFAULT_TARGET but can be overwritten
    # 'sort' means organizing into year/date tree, and this implies "fixing" an existing, possibly incorrect, year/date tree

    logging.basicConfig(level=logging._nameToLevel[loglevel.upper()])

    cfg = {
        'dry_run': dry_run,
        'smoke_test': smoke_test,
        'preserve_folders': preserve_folders,
        'exclude_descriptive': exclude_descriptive,
        'filing_preference': filing_preference,
        'target_base_folder': target,
        'mask': mask,
        'from_date': from_date,
        'exact_matches_folder': EXACT_MATCHES_FOLDER,
        'user_source': user_source,
        'transfer_method': transfer_method
    }

    pb = PhotoBinner(**cfg)

    if setup_only:
        exit(0)
    
    cont = input("Continue? y/N ")
    if str(cont) != 'y':
        exit(0)

    pb.run()

if __name__ == "__main__":
    main()
