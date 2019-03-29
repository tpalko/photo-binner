#!/usr/bin/python

import os
import sys
from  datetime import datetime, timedelta
from pytz import timezone
import click
import logging
import re
import hashlib
import shutil
import pprint
from exifwrapper import ExifWrapper
import json
from source import Source
from logescrow import LogEscrow
import importlib
import glob
from ConfigParser import ConfigParser
from logescrow import LogEscrow

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

config = ConfigParser()
config.read('./photobinner.cfg')

IMAGE_MAKERS = ['Apple']

DEFAULT_TARGET = config.defaults()['target']
DEFAULT_MASK = "*"
EXACT_MATCHES_FOLDER = config.get('folders', 'exact_matches')

UTC = timezone("UTC")
TZ = timezone(config.get('locale', 'timezone'))
EPOCH = datetime(1970, 1, 1)
UTC_EPOCH = UTC.localize(EPOCH)
LOCAL_EPOCH = UTC_EPOCH.astimezone(TZ)
DEFAULT_YEARS = [1970, 1980]

# INBOX_PATHS = [
#     '/media/storage/pics/mobile_inbox',
#     '/media/storage/pics/inbox'
# ]

RUN_STATS = {
    'moves': {},
    'date_sources': {},
    'anomalies': {}
}

class PhotoBinner(object):

    def __init__(self, *args, **kwargs):
        self.log_escrow = LogEscrow(name=__name__)

    def _push_run_stat(self, type, key, value):
        if key not in RUN_STATS[type]:
            RUN_STATS[type][key] = []
        RUN_STATS[type][key].append(value)

    def _increment_run_stat(self, cat, current_folder, target_folder):
        if current_folder not in RUN_STATS['moves']:
            RUN_STATS['moves'][current_folder] = {}
        if target_folder not in RUN_STATS['moves'][current_folder]:
            RUN_STATS['moves'][current_folder][target_folder] = 0
        RUN_STATS['moves'][current_folder][target_folder] += 1
        # base = RUN_STATS[cat]
        # for k in kwargs:
        #     if kwargs[k] not in base:
        #         base[kwargs[k]] = {}
        #     base = base[kwargs[k]]
        # if type(base).__name__ == 'dict':
        #     base = 0
        # base = base + 1

    # - http://stackoverflow.com/questions/3431825/generating-an-md5-checksum-of-a-file
    def _md5(self, fname):
        hash_md5 = hashlib.md5()
        with open(fname, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()

    def move(self, src, dest, time_tuple):
        shutil.move(src, dest)
        os.utime(dest, (time_tuple[0], time_tuple[1]))

    def copy(self, src, dest, time_tuple):
        shutil.copy2(src, dest)

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

    def _extract_descriptive(self, full_path, mountpoint, exclude_descriptive):
        ew = ExifWrapper(filepath=full_path)
        all_metadata = ew.all_values()
        if 'image_make' in all_metadata and 'image_model' in all_metadata and all_metadata['image_make'] in IMAGE_MAKERS:
            # -- Apple
            # -- iPhone 5
            make_and_model = "%s_%s" % (all_metadata['image_make'], all_metadata['image_model'])
        else:
            # /media/storage/pics/whackamole/IMG_0001.JPG
            this_file = full_path.replace(mountpoint, '') if mountpoint else full_path
            # whackamole/IMG_0001.JPG
            parts = this_file.rpartition('/')
            # ['whackamole', '/', 'IMG_0001.JPG']
            self.log_escrow.debug(" - descriptive parts: %s" % parts[0])
            descriptive = parts[0]
            # whackamole
            descriptive = re.sub('^\/?dupe\/[0-9]+', '', descriptive)
            # -- remove YYYY, YYYY-MM-DD, YYYY_MM_DD, YYYYMMDD if the part is ENTIRELY that
            non_date_descriptive = [ d for d in descriptive.split('/') if d and not re.match('^[0-9]{8}$', d) and not re.match('^[0-9]{4}$', d) and not re.match('^[0-9]{4}[-_]{1}[0-9]{2}[-_]{1}[0-9]{2}$', d) ]
            # -- remove YYYY-MM-DD substrings
            non_date_descriptive = [ re.sub("[0-9]{4}-[0-9]{2}-[0-9]{2}", "", d).strip() for d in non_date_descriptive ]
            if exclude_descriptive:
                for e in exclude_descriptive:
                    non_date_descriptive = [ d for d in non_date_descriptive if not re.match('^%s$' % e, d) ]
            descriptive = "_".join([ d.replace(' ', '_') for d in non_date_descriptive ]) if len(non_date_descriptive) > 0 else None
            self.log_escrow.debug(" - descriptive: %s" % ( "'%s'" % descriptive if descriptive else None ))
        return descriptive

    def _extract_date_from_path(self, full_path):
        path = full_path.rpartition('/')[0]
        date_matches = []
        date_matches.extend([ datetime.strptime(m, '%Y_%m_%d') for m in re.findall('[0-9]{4}_{1}[0-9]{2}_{1}[0-9]{2}', path) ])
        date_matches.extend([ datetime.strptime(m, '%Y-%m-%d') for m in re.findall('[0-9]{4}-{1}[0-9]{2}-{1}[0-9]{2}', path) ])
        date_matches.sort()
        return TZ.localize(date_matches[0]) if len(date_matches) > 0 else None

    def _extract_date_from_filename(self, full_path):
        self.log_escrow.debug(" - trying to match timestamp from filename: %s" % full_path)
        match = re.search('[0-9]{8}[\_-]{1}[0-9]{6}', full_path)
        filename_date = None
        if match:
            self.log_escrow.debug(" - filename timestamp: %s" % match.group())
            filename_timestamp = match.group()
            if filename_timestamp.find('_') > 0:
                filename_date = TZ.localize(datetime.strptime(filename_timestamp, "%Y%m%d_%H%M%S"))
            elif filename_timestamp.find('-') > 0:
                filename_date = TZ.localize(datetime.strptime(filename_timestamp, "%Y%m%d-%H%M%S"))
            else:
                logger.fatal("- timestamp %s extracted from filename but datetime format not expected" % filename_timestamp)
            #calculated_timestamp = datetime.strftime(filename_date, "%Y-%m-%d %H:%M:%S")
            #calculated_date = datetime.strftime(filename_date, "%Y-%m-%d")
        else:
            self.log_escrow.debug(" - no filename match for timestamp")
        return filename_date

    def _get_target_date(self, current_path):

        file_stats = os.stat(current_path)
        # -- this assumed file was read as UTC, which is was not
        #target_date = UTC.localize(datetime.fromtimestamp(file_stats.st_mtime)).astimezone(TZ)
        # -- call file stats in local time
        target_date_from_stat = TZ.localize(datetime.fromtimestamp(file_stats.st_mtime))
        target_atime = file_stats.st_atime
        target_mtime = file_stats.st_mtime

        target_date_from_filename = self._extract_date_from_filename(current_path)

        target_date_from_path = self._extract_date_from_path(current_path)

        ew = ExifWrapper(filepath=current_path)
        target_date_from_exif = ew.image_datetime()

        # - in images from iphone backups, the timestamp of the file itself is accurate
        # - while the exif metadata is incorrect and may represent the date of backup
        # - this sequence of assignment assumes the most obvious data
        # - and elects more precise data if and when it is found
        # - note that each timestamp source (stat, filename, exif)
        # - have been observed to be incorrect in at least one case
        # - case: exif date is newer than file date for a group of files, file date is correct
        # - case: filename date is incorrect, does not agree with exif date

        stat_date_as_utc = target_date_from_stat.astimezone(UTC)
        self.log_escrow.debug(" - stat_date_as_utc: %s" % stat_date_as_utc)
        if target_date_from_exif and datetime.strftime(stat_date_as_utc, "%Y-%m-%d %H:%M") == datetime.strftime(target_date_from_exif, "%Y-%m-%d %H:%M"):
            self.log_escrow.warn(" - file date is double timezoned")
            # - basically add back (once) the hours of the local offset - it was offset twice
            target_date_from_stat = target_date_from_stat + timedelta(hours=-target_date_from_stat.utcoffset().total_seconds()/(60*60))
            target_mtime = (target_date_from_stat - LOCAL_EPOCH).total_seconds()
            self._push_run_stat('anomalies', 'file-date-double-timezoned', current_path)

        target_dates = [
            {'source': 'stat', 'date': target_date_from_stat},
            {'source': 'filename', 'date': target_date_from_filename},
            {'source': 'exif', 'date': target_date_from_exif}
        ]

        target_dates = [ d for d in target_dates if d['date'] ]
        target_dates.sort(key=lambda x: x['date'])
        target_dates_log = [ "%s: %s" % (t['source'], datetime.strftime(t['date'], "%Y-%m-%d %H:%M:%S %z")) for t in target_dates ]
        self.log_escrow.debug(" - %s" % target_dates_log)

        # - start by assuming the file is correct, and we'll refine below
        target_date = target_date_from_stat
        target_date_assigned_from = 'stat'

        if target_date_from_exif and target_date_from_stat and (target_date_from_exif - target_date_from_stat).total_seconds() > 1:
            self.log_escrow.warn(" - exif (%s) is newer than stat (%s) - iPhone?" % (datetime.strftime(target_date_from_exif, "%Y-%m-%d %H:%M:%S %z"), datetime.strftime(target_date_from_stat, "%Y-%m-%d %H:%M:%S %z")))
            self._push_run_stat('anomalies', 'recent-exif', current_path)

        # if target_date_from_path and target_date_from_path.year not in DEFAULT_YEARS \
        #     and target_date_from_path < target_date:
        #         target_date = target_date_from_path
        #         target_date_assigned_from = 'path'

        if target_date_from_filename and target_date_from_filename.year not in DEFAULT_YEARS:
            target_date = target_date_from_filename
            target_date_assigned_from = 'filename'

        if target_date_from_exif and target_date_from_exif.year not in DEFAULT_YEARS:
            if target_date_from_exif <= target_date or target_date.year in DEFAULT_YEARS:
                target_date = target_date_from_exif
                target_date_assigned_from = 'exif'

        self.log_escrow.warn(" - target date assigned using %s: %s" % (target_date_assigned_from, datetime.strftime(target_date, "%Y-%m-%d %H:%M:%S %z")))
        self._push_run_stat('date_sources', target_date_assigned_from, current_path)

        if target_date.year in DEFAULT_YEARS:
            self.log_escrow.warn(" - target date almost surely invalid (%s)" % (datetime.strftime(target_date, "%Y-%m-%d")))
            self._push_run_stat('anomalies', 'no-valid-date', current_path)

        # -- atime/mtime are by default what is already on the file
        # -- we want to avoid changing this unless it's completely wrong
        if target_date != target_date_from_stat:
            old_file_time = datetime.strftime(target_date_from_stat, "%Y-%m-%d %H:%M:%S %z")
            new_file_time = datetime.strftime(target_date, "%Y-%m-%d %H:%M:%S %z")
            self.log_escrow.warn(" - file time incorrect: %s -> %s" % (old_file_time, new_file_time))
            target_timestamp = (target_date - LOCAL_EPOCH).total_seconds()
            #target_atime = target_timestamp
            target_mtime = target_timestamp

        self.log_escrow.debug(" - atime: %s" % datetime.strftime(TZ.localize(datetime.fromtimestamp(target_atime)), "%Y-%m-%d %H:%M:%S %z"))
        self.log_escrow.debug(" - mtime: %s" % datetime.strftime(TZ.localize(datetime.fromtimestamp(target_mtime)), "%Y-%m-%d %H:%M:%S %z"))

        new_filename = None

        if target_date_from_filename and target_date and (target_date_from_filename - target_date).total_seconds() > 1:
            filename = current_path.rstrip('/').rpartition('/')[-1]
            file_prefix = filename.split('_')[0]
            file_suffix = filename.split('.')[-1]
            new_filename_stamp = datetime.strftime(target_date, "%Y%m%d_%H%M%S")
            new_filename = "%s_%s.%s" %(file_prefix, new_filename_stamp, file_suffix)
            self.log_escrow.warn(" - timestamp extracted from filename does not match calculated timestamp, renaming %s -> %s" % (filename, new_filename))
            self._push_run_stat('anomalies', 'filename-date-incorrect', current_path)

        if target_date_from_path and datetime.strftime(target_date_from_path, "%Y-%m-%d") != datetime.strftime(target_date, "%Y-%m-%d"):
            self.log_escrow.warn(" - date extracted from path %s does not match calculated date %s" % (datetime.strftime(target_date_from_path, "%Y-%m-%d"), datetime.strftime(target_date, "%Y-%m-%d")))
            self._push_run_stat('anomalies', 'path-date-incorrect', current_path)

        return (target_date, target_atime, target_mtime, new_filename, target_date_assigned_from,)

    def _determine_move_action(self, current_path, target_folder, filename):

        move_necessary = False
        move_action = "not determined"
        new_path = os.path.join(target_folder, filename)

        if current_path == new_path:
            move_action = " - current path is correct, matches calculated target"
        elif os.path.exists(new_path):
            self.log_escrow.info(" - another file exists at destination path, comparing files..")
            if self._md5(current_path) == self._md5(new_path):
                self.log_escrow.info(" - file at destination path is exact, moving to %s" % EXACT_MATCHES_FOLDER)
                target_folder = EXACT_MATCHES_FOLDER
                new_path = os.path.join(target_folder, filename)
                move_action = "exact match at target, moving to %s" % target_folder
                self._push_run_stat('anomalies', 'content-match-at-target', current_path)
            else:
                self.log_escrow.info(" - file at destination path is different, we have a duplicate")
                move_necessary = True
                dupe_count = 0
                dupe_folder = target_folder
                # - calculate dupe path if filename already exists
                while os.path.exists(new_path):
                    dupe_folder = os.path.join(target_folder, "dupe", str(dupe_count))
                    new_path = os.path.join(dupe_folder, filename)
                    move_action = "filename match, modifying new path -> %s" % new_path
                    if os.path.exists(new_path) and current_path == new_path and self._md5(current_path) == self._md5(new_path):
                        move_action = " - this file already exists as a duplicate"
                        move_necessary = False
                        break
                    dupe_count = dupe_count + 1
                target_folder = dupe_folder
                self._push_run_stat('anomalies', 'filename-match-at-target', current_path)
        else:
            move_action = "normal move %s -> %s" % (current_path, new_path)
            move_necessary = True

        return (target_folder, move_necessary, move_action,)

    def process_file(self, current_path, source, dry_run):

        if not current_path:
            current_path = source.mountpoint

        current_path_parts = current_path.rpartition('/')
        current_folder = current_path_parts[0]
        filename = current_path_parts[-1]

        self.log_escrow.clear_log_escrow()

        # - if DEBUG or INFO, logs immediately, otherwise requires a file change
        # - implies that outside the file change block, logs must be < WARN
        heading_log_event = None if self.log_escrow.logger.isEnabledFor(logging.INFO) else 'move_necessary'
        self.log_escrow.warn("", event=heading_log_event)
        self.log_escrow.warn("Processing %s.." % current_path, event=heading_log_event)

        (target_date, target_atime, target_mtime, new_filename, target_date_assigned_from,) = self._get_target_date(current_path)

        if not target_date:
            self.log_escrow.fatal(" - no target date could be calculated")
            return

        descriptive = self._extract_descriptive(current_path, source.mountpoint, source.exclude_descriptive)

        if new_filename:
            filename = new_filename

        # -- deriving working values
        year_string = datetime.strftime(target_date, "%Y")
        date_string = datetime.strftime(target_date, "%Y-%m-%d")
        descriptive_date = "%s_%s" %(date_string, descriptive) if descriptive else date_string

        # -- working values
        target_folder = os.path.join(TARGET, year_string, descriptive_date)
        (target_folder, move_necessary, move_action,) = self._determine_move_action(current_path, target_folder, filename)
        new_path = os.path.join(target_folder, filename)

        if move_necessary:
            self.log_escrow.release_log_escrow(trigger='move_necessary')
            self.log_escrow.warn(" - %s" % move_action)
            self._increment_run_stat('moves', current_folder=current_folder, target_folder=target_folder)

            if dry_run:
                self.log_escrow.debug(" - dry run, no action")
            else:
                # - actually move the file and fix timestamps
                # - create final path
                if not os.path.isdir(target_folder):
                    os.makedirs(target_folder)

                file_stats = os.stat(current_path)
                self.log_escrow.info(" - %s MB" % str(int(file_stats.st_size)/(1024*1024)))
                source.transfer_method(current_path, new_path, (target_atime, target_mtime,))
        else:
            self.log_escrow.warn(" - %s" % move_action)

        # - calculate various companion filenames
        xmp_filename = "%s.xmp" % filename
        crw_hidden_filename = "._%s" % filename
        crw_thm_filename = re.sub(r'\.CRW$', ".THM", filename) if filename[-4:] == ".CRW" else None
        avi_thm_filename = re.sub(r'\.AVI$', ".THM", filename) if filename[-4:] == ".AVI" else None

        for variant in [xmp_filename, crw_hidden_filename, crw_thm_filename, avi_thm_filename]:
            if not variant:
                continue
            variant_filepath = os.path.join(current_folder, variant)
            if not os.path.exists(variant_filepath):
                continue
            self.log_escrow.debug(" - processing existing variant %s" % variant)
            #_log_escrow(logging.DEBUG, "    - variant exists: %s" % variant)
            new_variant_filepath = os.path.join(target_folder, variant)
            self.log_escrow.debug("   - %s -> %s" % (variant_filepath, new_variant_filepath))
            if not dry_run and move_necessary:
                move(variant_filepath, new_variant_filepath)

@click.command()
@click.option('--source', '-s', 'user_source', help='Source folder')
@click.option('--target', '-t', 'target', default=DEFAULT_TARGET, help='Target folder, default "%s"' % DEFAULT_TARGET)
@click.option('--mask', '-m', 'mask', default=DEFAULT_MASK, help='Filename mask, default %s' % DEFAULT_MASK)
@click.option('--from-date', '-f', 'from_date', type=click.DateTime(), default=None, help='(Android Only) Process files only newer than this date (YYYY-MM-DD), default empty')
@click.option('--dry-run', '-d', 'dry_run', is_flag=True, help='Only print what would happen. Make no filesystem changes.')
@click.option('--setup-only', '-o', 'setup_only', is_flag=True, help='Run everything up to the actual processing of files.')
@click.option('--loglevel', '-l', 'loglevel', default='info', help='Logging level (debug, info, warn, error, fatal)')
def main(user_source, target, mask, from_date, dry_run, setup_only, loglevel):

    '''
    use cases:
        - import images from mounted SD card/USB stick/mobile device
            $ ./pic_date_sorter.py -i
        - sort images in place
        - sort images from one location to another
    these can be combined into a single operation: grab files from somewhere and sort them either in-place or to another location
        source defaults to searching for a mounted device but can be overwritten
        target defaults to DEFAULT_TARGET but can be overwritten
    'sort' means organizing into year/date tree, and this implies "fixing" an existing, possibly incorrect, year/date tree
    '''

    logger = logging.getLogger(__name__)
    sourcelogger = logging.getLogger('source')
    exifwrapperlogger = logging.getLogger('exifwrapper')

    loggers = [
        logger,
        sourcelogger,
        exifwrapperlogger
    ]

    loglevel = int(logging._levelNames[loglevel.upper()])

    # - at the top?
    logging.basicConfig(level=loglevel)
    # - or each ?
    # for l in loggers:
    #     l.setLevel(loglevel)

    SOURCE_TYPES = {}
    AUX_SOURCES = {}
    for g in glob.glob("sources/*.py"):
        if g == "sources/__init__.py":
            continue
        # module_name = g.replace("/", ".").rpartition(".")[0]
        # module = importlib.import_module(module_name)
        # source_class = module.classdef()
        source_class = importlib.import_module(g.replace("/", ".").rpartition(".")[0]).classdef()
        source_name = source_class().__class__.__name__
        SOURCE_TYPES[source_name] = source_class
        Source.register(source_class)

    pb = PhotoBinner()

    for section_name in [ s for s in config.sections() if s.startswith('Source-') ]:
        source_config = dict(config.items(section_name))
        source_name = section_name.rpartition('-')[-1]
        source_type = source_config['type']
        if source_type not in SOURCE_TYPES:
            logger.warn("Configured source with type '%s' is not represented by a Source implementation")
            continue
        if 'exclude_descriptive' in source_config:
            source_config['exclude_descriptive'] = source_config['exclude_descriptive'].split(',')
        if 'transfer_method' in source_config:
            source_config['transfer_method'] = pb.move if source_config['transfer_method'] == 'move' else pb.copy
        AUX_SOURCES[source_name] = SOURCE_TYPES[source_type](**source_config)

    source = None

    if user_source:
        if user_source in AUX_SOURCES.keys():
            print("Attempting source: %s" % user_source)
            if AUX_SOURCES[user_source].verify(mask=mask, from_date=from_date):
                source = AUX_SOURCES[user_source]
        else:
            source_folder = SOURCE_TYPES['Folder'](mountpoint=user_source, transfer_method=pb.move)
            print("Attempting source: %s" % user_source)
            if source_folder.verify(mask=mask, from_date=from_date):
                source = source_folder
    else:
        for s in AUX_SOURCES.keys():
            print("Attempting source: %s" % s)
            if AUX_SOURCES[s].verify(mask=mask, from_date=from_date):
                logger.info("%s verified" % s)
                source = AUX_SOURCES[s]
            if source:
                break

    if not source:
        print("No source provided or found")
        exit(1)

    if mask != DEFAULT_MASK:
        logger.info("Filtering by '%s'" % mask)

    global TARGET
    TARGET = target

    if not os.path.exists(EXACT_MATCHES_FOLDER):
        os.makedirs(EXACT_MATCHES_FOLDER)

    # - if no ending slash on source, append one
    # if not os.path.isfile(source.mountpoint) and source.mountpoint[-1] != os.sep:
    #    self. _log_escrow(logging.DEBUG, "Fixing source.mountpoint with %s.." % os.sep)
    #     source.mountpoint = "%s%s" % (source.mountpoint, os.sep)

    if source.mountpoint and os.path.isfile(source.mountpoint):
        logger.info("Processing %s " % source.mountpoint)
        pb.process_file(source=source, dry_run=dry_run)
    else:
        logger.info("Processing paths from source..")
        for current_path in source.paths(mask=mask, from_date=from_date):
            pb.process_file(current_path=current_path, source=source, dry_run=dry_run)

    out_filename = 'out/sorter_%s%s.out' % (datetime.strftime(datetime.now(), "%Y%m%d_%H%M%S"), '_dry_run' if dry_run else '')
    with open(out_filename, 'wb') as f:
        f.write(json.dumps(RUN_STATS, indent=4, sort_keys=True))
    #pprint.pprint(RUN_STATS, indent=4)

if __name__ == "__main__":
    main()
