#!/usr/bin/env python

import os
import sys
import signal
from datetime import datetime, timedelta
from pytz import timezone
import click
import logging
import re
import hashlib
import shutil
import pprint
import json
#import importlib
import glob
from configparser import ConfigParser
from pwd import getpwnam
import traceback
#from grp import getgrnam
print(sys.path)
from photobinner.sources.source import StitchFolder, SourceFile
from photobinner.exifwrapper import ExifWrapper
from photobinner.logescrow import LogEscrow


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

# -- EXIF 'image_make' in this list get descriptive text <make>_<model>
IMAGE_MAKERS = ['Apple']

DEFAULT_TARGET = config.defaults()['target']
DEFAULT_MASK = "*"
EXACT_MATCHES_FOLDER = config.get('folders', 'exact_matches')
COPY_EXACT_MATCHES = config.getboolean('folders', 'copy_exact_matches')

UTC = timezone("UTC")
TZ = timezone(config.get('locale', 'timezone'))
EPOCH = datetime(1970, 1, 1)
UTC_EPOCH = UTC.localize(EPOCH)
LOCAL_EPOCH = UTC_EPOCH.astimezone(TZ)
DEFAULT_YEARS = [1970, 1980]

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
    sessionfile = None
    session = True

    run_stats = {
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

    def __init__(self, *args, **kwargs):
        for k in kwargs:
            logger.debug("Setting %s -> %s" % (k, kwargs[k]))
            self.__setattr__(k, kwargs[k])
        for v in [ v for v in dir(self) if v.find("_") != 0 ]:
            t = type(self.__getattribute__(v))
            if t in [str, int, bool, str] or not t:
                logger.debug("%s: %s" % (v, self.__getattribute__(v)))
        self.log_escrow = LogEscrow(name=__name__)
        self._initialize()

    def _md5(self, fname):
        hash_md5 = hashlib.md5()
        with open(fname, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()

    def _hash_equal(self, path1, path2):
        return self._md5(path1) == self._md5(path2)

    def _push_run_stat(self, type, key, value):
        if key not in self.run_stats[type]:
            self.run_stats[type][key] = []
        self.run_stats[type][key].append(value)

    def _increment_run_stat(self, cat, current_folder, target_folder=None):
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

    def _extract_descriptive(self, sourcefile, mountpoint, exclude_descriptive):
        descriptive = None
        ew = ExifWrapper(filepath=sourcefile.working_path)
        all_metadata = ew.all_values()
        if 'image_make' in all_metadata and 'image_model' in all_metadata and all_metadata['image_make'] in IMAGE_MAKERS:
            # -- Apple
            # -- iPhone 5
            descriptive = "%s_%s" % (all_metadata['image_make'], all_metadata['image_model'])
        elif mountpoint:
            # -- use preserve_folders count to save that number of parent folders in the source's base path
            # -- the file may be nested deep, and we're by default going to use all folder names between it and the base path for descriptive text search
            # -- but by default, the base path gets chucked
            # -- preserve_folders saves that number of parent folders from the base path
            # --
            # -- /original/path/given/some/interesting/detail/of/file.jpg <= full_path
            # -- /original/path/given/ <= mountpoint
            # -- preserve_folders = 0 ->            some/interesting/detail/of/file.jpg
            # -- preserve_folders = 2 -> path/given/some/interesting/detail/of/file.jpg

            path_to_chuck = mountpoint.rstrip('/')
            for i in range(self.preserve_folders):
                path_to_chuck = path_to_chuck.rpartition('/')[0]
            base_removed = sourcefile.original_path.replace(path_to_chuck, '') if path_to_chuck else sourcefile.original_path
            descriptive_path = base_removed.rpartition('/')[0]
            self.log_escrow.debug(" - descriptive path: %s" % descriptive_path)

            # -- remove leading /dupe/nnn
            if re.search('\/?dupe\/[0-9]+', descriptive_path):
                descriptive_path = re.sub("\/?dupe\/[0-9]+", "", descriptive_path)
            descriptive_folders = [ f for f in descriptive_path.split('/') if f ]

            self.log_escrow.debug(" - descriptive folders: %s" % descriptive_folders)

            descriptive_remove_regexp = ['^[0-9]{8}$', '^[0-9]{4}$', '^[0-9]{4}[-_]{1}[0-9]{2}[-_]{1}[0-9]{2}$']#, '[0-9]{4}-[0-9]{2}-[0-9]{2}']
            if exclude_descriptive and len(exclude_descriptive) > 0:
                descriptive_remove_regexp.extend(exclude_descriptive)
            self.log_escrow.debug(" - descriptive remove regexps: %s" % ",".join(descriptive_remove_regexp))
            for r in [ r for r in descriptive_remove_regexp if r ]:
                descriptive_folders = [ d for d in descriptive_folders if d and not re.match(r, d) ]

            self.log_escrow.debug(" - descriptive folders: %s" % descriptive_folders)

            descriptive_sub_regexp = [("[0-9]{4}_[0-9]{2}_[0-9]{2}", " "), ("[0-9]{4}-[0-9]{2}-[0-9]{2}", " "), ("-", " "), ("\s{2,}", " ")]
            self.log_escrow.debug(" - descriptive sub regexp: %s" % ",".join([ "%s -> \"%s\"" % (s[0], s[1]) for s in descriptive_sub_regexp ]))
            for s in descriptive_sub_regexp:
                descriptive_folders = [ re.sub(s[0], s[1], d).strip() for d in descriptive_folders if d ]

            self.log_escrow.debug(" - descriptive folders: %s" % descriptive_folders)
            tokens = []
            for d in descriptive_folders:
                tokens.extend([ d.strip().rstrip("_").lstrip("_") for d in d.split(' ') if d ])

            self.log_escrow.debug(" - tokens: %s" % tokens)

            unique_tokens = []
            for t in tokens:
                if t not in unique_tokens:
                    unique_tokens.append(t)

            descriptive = "_".join(unique_tokens) if len(unique_tokens) > 0 else None
            self.log_escrow.debug(" - descriptive: %s" % ( "'%s'" % descriptive if descriptive else None ))

        return descriptive

    def _extract_date_from_path(self, sourcefile):
        path = sourcefile.original_path.rpartition('/')[0]
        date_matches = []
        date_matches.extend([ datetime.strptime(m, '%Y_%m_%d') for m in re.findall('[0-9]{4}_{1}[0-9]{2}_{1}[0-9]{2}', path) ])
        date_matches.extend([ datetime.strptime(m, '%Y-%m-%d') for m in re.findall('[0-9]{4}-{1}[0-9]{2}-{1}[0-9]{2}', path) ])
        date_matches.sort()
        self.log_escrow.debug(" - dates from path: %s" % [ datetime.strftime(d, "%Y-%m-%d %H:%M:%S %z") for d in date_matches ])
        return TZ.localize(date_matches[0]) if len(date_matches) > 0 else None

    def _extract_date_from_filename(self, sourcefile):
        self.log_escrow.debug(" - trying to match timestamp from filename: %s" % sourcefile.original_path)
        match = re.search('[0-9]{8}[\_-]{1}[0-9]{6}', sourcefile.original_path)
        filename_date = None
        if match:
            self.log_escrow.debug(" - filename timestamp: %s" % match.group())
            filename_timestamp = match.group()
            if filename_timestamp.find('_') > 0:
                filename_date = TZ.localize(datetime.strptime(filename_timestamp, "%Y%m%d_%H%M%S"))
            elif filename_timestamp.find('-') > 0:
                filename_date = TZ.localize(datetime.strptime(filename_timestamp, "%Y%m%d-%H%M%S"))
            else:
                self.log_escrow.warn("- timestamp %s extracted from filename but datetime format not expected" % filename_timestamp)
            #calculated_timestamp = datetime.strftime(filename_date, "%Y-%m-%d %H:%M:%S")
            #calculated_date = datetime.strftime(filename_date, "%Y-%m-%d")
        else:
            self.log_escrow.debug(" - no filename match for timestamp")
        return filename_date

    def _date_match(self, d1, d2):
        return d1.year == d2.year and d1.month == d2.month and d1.day == d2.day

    def _is_day_only(self, d):
        return d.hour == 0 and d.minute == 0 and d.second == 0

    def _get_target_date(self, sourcefile):

        file_stats = os.stat(sourcefile.working_path)
        # -- this assumed file was read as UTC, which is was not
        #target_date = UTC.localize(datetime.fromtimestamp(file_stats.st_mtime)).astimezone(TZ)
        # -- call file stats in local time
        target_date_from_stat = TZ.localize(datetime.fromtimestamp(file_stats.st_mtime))
        target_atime = file_stats.st_atime
        target_mtime = file_stats.st_mtime

        target_date_from_filename = self._extract_date_from_filename(sourcefile)

        target_date_from_path = self._extract_date_from_path(sourcefile)

        ew = ExifWrapper(filepath=sourcefile.working_path)
        target_date_from_exif = ew.image_datetime()

        # - in images from iphone backups, the timestamp of the file itself is accurate
        # - while the exif metadata is incorrect and may represent the date of backup
        # - the following sequence of assignment assumes the most obvious data
        # - and elects more precise data if and when it is found
        # - note that each timestamp source (stat, filename, exif)
        # - have been observed to be incorrect in at least one case
        # - case: exif date is newer than file date for a group of files, file date is correct
        # - case: filename date is incorrect, does not agree with exif date

        stat_date_as_utc = target_date_from_stat.astimezone(UTC)
        self.log_escrow.debug(" - stat_date_as_utc: %s" % stat_date_as_utc)

        # -- if the stat date, which is timezone-aware, taken as UTC equals the exif date
        # -- then ...
        if target_date_from_exif and datetime.strftime(stat_date_as_utc, "%Y-%m-%d %H:%M") == datetime.strftime(target_date_from_exif, "%Y-%m-%d %H:%M"):
            self.log_escrow.warn(" - file date is double timezoned")
            # - basically add back (once) the hours of the local offset - it was offset twice
            target_date_from_stat = target_date_from_stat + timedelta(hours=-target_date_from_stat.utcoffset().total_seconds()/(60*60))
            target_mtime = (target_date_from_stat - LOCAL_EPOCH).total_seconds()
            self._push_run_stat('anomalies', 'file-date-double-timezoned', sourcefile.original_path)

        target_dates = {
            'stat': target_date_from_stat,
            'filename': target_date_from_filename,
            'exif': target_date_from_exif,
            'path': target_date_from_path
        }

        # -- filter out empty or invalid values
        target_dates = { d: target_dates[d] for d in target_dates if target_dates[d] and target_dates[d].year not in DEFAULT_YEARS }

        # -- if two date sources are the same day but one lacks time, remove it
        remove_sources = []
        for is_day_only in target_dates:
            if self._is_day_only(target_dates[is_day_only]):
                for same_day in [ d for d in target_dates if d != is_day_only ]:
                    if self._date_match(target_dates[is_day_only], target_dates[same_day]) and not self._is_day_only(target_dates[same_day]):
                        remove_sources.append(is_day_only)
                        self.log_escrow.debug(" - excluding %s source as it has no time information and %s matches the date" % (is_day_only, same_day))
                        break
        target_dates = { d: target_dates[d] for d in target_dates if d not in remove_sources }

        # -- log the sorted list of candidates
        target_dates_log = [ { t: datetime.strftime(target_dates[t], "%Y-%m-%d %H:%M:%S %z") } for t in sorted(target_dates, key=lambda x: target_dates[x]) ]
        self.log_escrow.debug(" - %s" % target_dates_log)

        # -- accounting for the possible one-second lag between metadata and inode information
        # -- if metadata is more recent, it suggests iPhone
        if target_date_from_exif and target_date_from_stat and (target_date_from_exif - target_date_from_stat).total_seconds() > 1:
            self.log_escrow.warn(" - exif (%s) is newer than stat (%s) - iPhone?" % (datetime.strftime(target_date_from_exif, "%Y-%m-%d %H:%M:%S %z"), datetime.strftime(target_date_from_stat, "%Y-%m-%d %H:%M:%S %z")))
            self._push_run_stat('anomalies', 'recent-exif', sourcefile.original_path)

        # -- order to assign dates (highest priority is last!)
        date_source_priority = ['stat', 'path', 'filename', 'exif']

        target_date = None

        for date_source in [ d for d in date_source_priority if d in target_dates ]:
            if not target_date or (date_source == 'filename' or target_dates[date_source] < target_date):
                target_date = target_dates[date_source]
                target_date_assigned_from = date_source

        self.log_escrow.info(" - target date assigned using %s: %s" % (target_date_assigned_from, datetime.strftime(target_date, "%Y-%m-%d %H:%M:%S %z")))
        self._push_run_stat('date_sources', target_date_assigned_from, sourcefile.original_path)

        if target_date.year in DEFAULT_YEARS:
            self.log_escrow.warn(" - target date almost surely invalid (%s)" % (datetime.strftime(target_date, "%Y-%m-%d")))
            self._push_run_stat('anomalies', 'no-valid-date', sourcefile.original_path)

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

        # -- if we've extracted a date from the filename (not path) and that date is different than the settled date
        # -- we're going to rename the file to match
        if target_date_from_filename and target_date and (target_date_from_filename - target_date).total_seconds() > 1:
            filename = sourcefile.original_path.rstrip('/').rpartition('/')[-1]
            file_prefix = filename.split('_')[0]
            file_suffix = filename.split('.')[-1]
            new_filename_stamp = datetime.strftime(target_date, "%Y%m%d_%H%M%S")
            new_filename = "%s_%s.%s" %(file_prefix, new_filename_stamp, file_suffix)
            self.log_escrow.warn(" - timestamp extracted from filename does not match calculated timestamp, renaming %s -> %s" % (filename, new_filename))
            self._push_run_stat('anomalies', 'filename-date-incorrect', sourcefile.original_path)

        # -- same deal as above but with the date found in the path, and we're just logging the fact, not renaming the folder
        if target_date_from_path and datetime.strftime(target_date_from_path, "%Y-%m-%d") != datetime.strftime(target_date, "%Y-%m-%d"):
            self.log_escrow.warn(" - date extracted from path %s does not match calculated date %s" % (datetime.strftime(target_date_from_path, "%Y-%m-%d"), datetime.strftime(target_date, "%Y-%m-%d")))
            self._push_run_stat('anomalies', 'path-date-incorrect', sourcefile.original_path)

        return (target_date, target_atime, target_mtime, new_filename, target_date_assigned_from,)

    def _determine_move_action(self, sourcefile, target_folder, filename):

        move_necessary = False
        move_action = "not determined"
        new_path = os.path.join(target_folder, filename)

        if sourcefile.original_path == new_path:
            move_action = " - current path is correct, matches calculated target, not moving"
        elif os.path.exists(new_path):
            self.log_escrow.warn(" - another file exists at destination path, comparing files..")
            if self._hash_equal(sourcefile.working_path, new_path):
                move_necessary = COPY_EXACT_MATCHES
                if move_necessary:
                    self.log_escrow.warn(" - file at destination path is exact, moving to %s" % self.exact_matches_folder)
                    target_folder = self.exact_matches_folder
                    new_path = os.path.join(target_folder, filename)
                    move_action = "exact match at target, moving to %s" % target_folder
                else:
                    self.log_escrow.warn(" - file at destination path is exact, not moving")
                self._push_run_stat('anomalies', 'content-match-at-target', sourcefile.original_path)
            else:
                self.log_escrow.warn(" - file at destination path is different, we have a duplicate")
                move_necessary = True
                dupe_count = 0
                dupe_folder = target_folder
                # - calculate dupe path if filename already exists
                while os.path.exists(new_path):
                    dupe_folder = os.path.join(target_folder, "dupe", str(dupe_count))
                    new_path = os.path.join(dupe_folder, filename)
                    move_action = "filename match, modifying new path -> %s" % new_path
                    if os.path.exists(new_path) and sourcefile.original_path == new_path and self._hash_equal(sourcefile.working_path, new_path):
                        move_action = " - this file already exists as a duplicate, not moving"
                        move_necessary = False
                        break
                    dupe_count = dupe_count + 1
                target_folder = dupe_folder
                self._push_run_stat('anomalies', 'filename-match-at-target', sourcefile.original_path)
        else:
            move_action = "normal move %s -> %s" % (sourcefile.original_path, new_path)
            move_necessary = True

        self.log_escrow.info(" - %s" % move_action)

        return (target_folder, move_necessary, )

    def _calculate_target_folder(self, source, target_date, descriptive):
        # -- deriving working values
        year_string = datetime.strftime(target_date, "%Y")
        date_string = datetime.strftime(target_date, "%Y-%m-%d")
        
        self.log_escrow.info(" - calculating target folder for source target: %s" % source.target)
        
        if self.filing_preference == 'label' and descriptive:
            return os.path.join(source.target, year_string, descriptive, date_string)
        elif descriptive:
            return os.path.join(source.target, year_string, "%s_%s" %(date_string, descriptive))
        else:
            return os.path.join(source.target, year_string, date_string)

    def _process_stitch_folder(self, source, stitch_folder):
        self.log_escrow.info("Processing stitch folder: %s" % stitch_folder.working_path)
        for stitch_file in [ g for g in glob.glob("%s/*" % stitch_folder.working_path) if re.search(STITCH_FILE_MATCH, g.rpartition('/')[-1]) ]:
            self.log_escrow.info(" - found stich file: %s" % stitch_file)
            stitch_file_source_file = SourceFile(stitch_file)
            (target_date, target_atime, target_mtime, new_filename, target_date_assigned_from,) = self._get_target_date(stitch_file_source_file)
            if not target_date:
                self.log_escrow.warn(" - no target date could be calculated")
                raise Exception("no target date could be calculated")
            stitch_folder_name = stitch_folder.working_path.rpartition('/')[-1]
            exclude_descriptive = source.exclude_descriptive.append(stitch_folder_name)
            descriptive = self._extract_descriptive(stitch_file_source_file, source.mountpoint, exclude_descriptive)
            target_folder = self._calculate_target_folder(source, target_date, descriptive)
            (target_folder, move_necessary,) = self._determine_move_action(stitch_folder, target_folder, stitch_folder_name)
            new_path = os.path.join(target_folder, stitch_folder_name)
            if move_necessary:
                if self.dry_run:
                    self.log_escrow.info(" - dry run, no action")
                else:
                    self.log_escrow.info(" - moving %s -> %s" % (stitch_folder.working_path, new_path))
                    source.transfer_method(stitch_folder.working_path, new_path)

    def _process_file(self, source, sourcefile):

        current_path_parts = sourcefile.original_path.rpartition('/')
        current_folder = current_path_parts[0]
        filename = current_path_parts[-1]

        self.log_escrow.clear_log_escrow()

        # - if DEBUG or INFO, logs immediately, otherwise requires a file change
        # - implies that outside the file change block, logs must be < WARN
        heading_log_event = None if self.log_escrow.logger.isEnabledFor(logging.INFO) else 'move_necessary'
        self.log_escrow.debug("", event=heading_log_event)
        self.log_escrow.info("Processing %s.." % sourcefile.original_path, event=heading_log_event)

        (target_date, target_atime, target_mtime, new_filename, target_date_assigned_from,) = self._get_target_date(sourcefile)

        if not target_date:
            self.log_escrow.warn(" - no target date could be calculated")
            raise Exception("no target date could be calculated")

        descriptive = self._extract_descriptive(sourcefile, source.mountpoint, source.exclude_descriptive)

        if new_filename:
            filename = new_filename

        target_folder = self._calculate_target_folder(source, target_date, descriptive)
        (target_folder, move_necessary,) = self._determine_move_action(sourcefile, target_folder, filename)
        new_path = os.path.join(target_folder, filename)

        if move_necessary:
            self.log_escrow.release_log_escrow(trigger='move_necessary')
            self._increment_run_stat('moves', current_folder=current_folder, target_folder=target_folder)

            if self.dry_run:
                self.log_escrow.info(" - dry run, no action")
            else:
                # - actually move the file and fix timestamps
                # - create final path
                if not os.path.isdir(target_folder):
                    os.makedirs(target_folder)
                    os.chown(target_folder, OWNER_UID, -1)

                file_stats = os.stat(sourcefile.working_path)
                self.log_escrow.info(" - %s MB" % str(int(file_stats.st_size)/(1024*1024)))
                source.transfer_method(sourcefile.working_path, new_path, (target_atime, target_mtime,))
        else:
            self._increment_run_stat('correct', current_folder=current_folder)

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
            self.log_escrow.info(" - processing existing variant %s" % variant['name'])
            new_variant_filepath = os.path.join(target_folder, variant['name'])
            self.log_escrow.info("   - %s -> %s" % (variant['path'], new_variant_filepath))
            if not self.dry_run and move_necessary:
                source.transfer_method(variant['path'], new_variant_filepath)

    '''
    Initialization Block
    '''

    source_types = {}
    verified_sources = {}
    attempt_sources = {}
    aux_sources = {}

    def _verify_chosen_sources(self):
        for s in self.attempt_sources:
            self.log_escrow.info("Verifying source: %s" % s)
            if self.attempt_sources[s].verify():
                self.log_escrow.info(" - verified!")
                self.verified_sources[s] = self.attempt_sources[s]
            else:
                self.log_escrow.info(" - not verified!")

        self.log_escrow.info("%s/%s sources verified: [%s]" % (len(list(self.verified_sources.keys())), len(list(self.attempt_sources.keys())), ",".join([ s for s in list(self.verified_sources.keys()) ])))

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
                    transfer_method=self.move,
                    exclude_descriptive=self.exclude_descriptive.split(','),
                    target=self.target_base_folder
                )
                self.attempt_sources[mountpoint] = source_folder
        else:
            for s in list(self.aux_sources.keys()):
                self.attempt_sources[s] = self.aux_sources[s]

        self.log_escrow.info("%s/%s sources selected: [%s]" % (len(list(self.attempt_sources.keys())), len(list(self.aux_sources.keys())), ",".join([ "%s (%s)" % (s, self.attempt_sources[s].type) for s in list(self.attempt_sources.keys()) ])))

    def _load_configured_sources(self):

        self.log_escrow.debug("Finding sources..")

        if self.mask != DEFAULT_MASK:
            self.log_escrow.warn("Filtering all sources by '%s'" % self.mask)

        # -- load configured source types
        for section_name in [ s for s in config.sections() if s.startswith('Source-') ]:
            self.log_escrow.debug(f'{section_name}..')
            source_config = dict(config.items(section_name))
            source_type = source_config['type']
            if source_type not in self.source_types:
                self.log_escrow.warn("Configured source with type '%s' is not represented by a Source implementation" % source_type)
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
                self.log_escrow.debug(" - target not defined, setting: %s" % (self.target_base_folder))
                source_config['target'] = self.target_base_folder
            else:
                self.log_escrow.debug(" - target defined: %s" % source_config['target'])
            
            # -- default instantiates a 'type' source with kwargs from the ini k/v
            self.aux_sources[source_name] = self.source_types[source_type](**source_config)

        self.log_escrow.info("%s source configurations found: [%s]" % (len(list(self.aux_sources.keys())), ",".join([ s for s in list(self.aux_sources.keys()) ])))

    def _load_source_types(self):
        self.log_escrow.debug("Loading source interfaces..")
        # from sources import android
        # self.source_types['Android'] = android.classdef()
        #mod = __import__("photobinner.sources")
        from photobinner.sources import sources 
        for source_class in sources():
            self.log_escrow.debug("Loading module: %s" % source_class)
            self.source_types[source_class().__class__.__name__] = source_class
            #Source.register(source_class)
        self.log_escrow.info("%s source interfaces configured: [%s]" % (len(list(self.source_types.keys())), ",".join([ s for s in list(self.source_types.keys()) ])))

    def _get_json_content(self, filepath):
        j = None
        with open(filepath, 'r') as o:
            filepath_contents = o.read()
            try:
                j = json.loads(filepath_contents)
            except:
                logger.warning(" - failed to load %s as JSON" % filepath)
        return j

    def _load_session(self):
        open_sessions = []

        logger.info("Gathering open sessions..")
        # -- gather up all the open sessions
        for outfile in [ g for g in glob.glob(os.path.join(STATS_FOLDER, "*")) if re.search("photobinner\_[0-9]{8}\_[0-9]{6}%s\_[A-Za-z0-9]+\.out$" % ('_dry_run' if self.dry_run else ''), g) ]:
            j = self._get_json_content(outfile)
            if j and 'meta' in j and 'status' in j['meta'] and j['meta']['status'] == 'open':
                logger.info(" - %s (open)" % outfile)
                open_sessions.append(outfile)
            else:
                logger.info(" - %s (not open)" % outfile)

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
            self.log_escrow.warn("Continuing session file: %s" % self.sessionfile)
            self.run_stats = self._get_json_content(self.sessionfile)
            self.run_stats['meta']['dry_run'] = self.run_stats['meta']['dry_run'] == 'true'
            if self.run_stats['meta']['dry_run'] != self.dry_run:
                self.log_escrow.warn("The selected session is%s a dry run, however the program was called with%s the dry run flag. Forcing the flag to match the file." % (' not' if not self.run_stats['meta']['dry_run'] else '', 'out' if not self.dry_run else ''))
                self.dry_run = self.run_stats['meta']['dry_run'] == 'true'
        elif session_choice.lower() == 's':
            self.run_stats['meta']['dry_run'] = 'true' if self.dry_run else 'false'
            self.session = False
            self.log_escrow.warn("Skipping session tracking")
        elif session_choice.lower() == 'n':
            good_name = None
            while(not good_name):
                print("Enter a name for the new session (numbers and letters only please):")
                session_name = input()
                if len([ t for t in session_name.split(' ') if not t.isalnum() ]) == 0:
                    good_name = session_name.replace(' ', '').lower()
            timestamp = datetime.strftime(datetime.now(), "%Y%m%d_%H%M%S")
            outfile_name = "photobinner_%s%s%s.out" % (timestamp, ('_dry_run' if self.dry_run else ''), "_%s" % good_name if good_name else "_unnamed")
            self.sessionfile = os.path.join(STATS_FOLDER, outfile_name)
            self.log_escrow.warn("Starting a new session file: %s" % self.sessionfile)
            self.run_stats['meta']['dry_run'] = 'true' if self.dry_run else 'false'
            with open(self.sessionfile, 'w') as s:
                s.write(json.dumps(self.run_stats))
        else: # session_choice.lower() == 'q':
            exit(0)

        # -- populated verified sources with processed files from previous runs
        for v in [ v for v in self.verified_sources if v in self.run_stats['processed_files'] ]:
            self.verified_sources[v].processed_files = self.run_stats['processed_files'][v]
            logger.info("Source: %s -> Found %s processed files" % (v, len(self.verified_sources[v].processed_files)))

    def _initialize(self):

        signal.signal(signal.SIGINT, self.sigint_handler())

        self._load_source_types()
        self._load_configured_sources()
        self._identify_chosen_sources()
        self._verify_chosen_sources()

        if len(list(self.verified_sources.keys())) == 0:
            logger.debug("No provided source could be verified")
            exit(1)

        if not os.path.exists(STATS_FOLDER):
            logger.info("Creating out folder: %s" % STATS_FOLDER)
            os.makedirs(STATS_FOLDER)
            os.chown(STATS_FOLDER, OWNER_UID, -1)
        else:
            logger.info("Out folder found: %s" % STATS_FOLDER)
        
        if not os.path.exists(self.exact_matches_folder):
            os.makedirs(self.exact_matches_folder)
            os.chown(self.exact_matches_folder, OWNER_UID, -1)

        self._load_session()

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
                self.log_escrow.fatal("Noticed sigint in main loop, breaking..")
                break
            run_stat = { 'source': s, 'start': datetime.strftime(datetime.now(), "%Y-%m-%dT%H:%M:%S"), 'file_count': 0 }
            try:
                if source.mountpoint and os.path.isfile(source.mountpoint):
                    self.log_escrow.info("Processing single file %s " % source.mountpoint)
                    try:
                        sourcefile = SourceFile(source.mountpoint)
                        self._process_file(source=source, sourcefile=sourcefile)
                        run_stat['file_count'] += 1
                        source.processed_files.append(source.mountpoint)
                    except:
                        self.log_escrow.error("Exception caught processing file: %s" % source.mountpoint)
                        self.log_escrow.error(str(sys.exc_info()[0]))
                        self.log_escrow.error(str(sys.exc_info()[1]))
                        traceback.print_tb(sys.exc_info()[2])
                else:
                    self.log_escrow.info("Processing paths from source..")
                    for sf in source.paths():
                        if self.sigint:
                            break
                        try:
                            if isinstance(sf, StitchFolder):
                                self._process_stitch_folder(source=source, stitch_folder=sf)
                            else:
                                self._process_file(source=source, sourcefile=sf)
                                run_stat['file_count'] += 1
                                source.processed_files.append(sf.original_path)
                                if count > 0:
                                    count -= 1
                                if count == 0:
                                    self.log_escrow.info("Smoke test limit (%s) reached" % self.smoke_test)
                                    break
                        except:
                            self.log_escrow.error("Exception caught processing file: %s (%s)" % (sf.working_path, sf.original_path))
                            self.log_escrow.error(str(sys.exc_info()[0]))
                            self.log_escrow.error(str(sys.exc_info()[1]))
                            traceback.print_tb(sys.exc_info()[2])
            except:
                run_stat['exception'] = str(sys.exc_info()[1])
                run_stat['stack_trace'] = str(traceback.extract_tb(sys.exc_info()[2]))
                self.log_escrow.error(str(sys.exc_info()[0]))
                self.log_escrow.error(str(sys.exc_info()[1]))
                traceback.print_tb(sys.exc_info()[2])

            self.log_escrow.info("Closing the run..")
            run_stat['stop'] = datetime.strftime(datetime.now(), "%Y-%m-%dT%H:%M:%S")
            self.run_stats['meta']['runs'].append(run_stat)

        self.log_escrow.info("Capturing processed files from sources..")
        for s in list(self.verified_sources.keys()):
            self.run_stats['processed_files'][s] = self.verified_sources[s].processed_files

        # -- thinking one file should be kept in perpetuity..
        #if not self.sigint and not 'exception' in run_stat:
        #    self.run_stats['meta']['status'] = 'closed'
        self.log_escrow.info("Processing session and writing out..")
        updated_session = json.dumps(self.run_stats, indent=4, sort_keys=True)

        if self.session:
            with open(self.sessionfile, 'w') as f:
                f.write(updated_session)

            os.chown(self.sessionfile, OWNER_UID, -1)
            #pprint.pprint(self.run_stats, indent=4)

            self.log_escrow.info("Session %s end" % self.sessionfile)
        else:
            print(updated_session)

        self.log_escrow.info("All operations complete.")

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
def main(user_source, target, mask, from_date, preserve_folders, exclude_descriptive, filing_preference, dry_run, smoke_test, setup_only, loglevel):

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
        'user_source': user_source
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
