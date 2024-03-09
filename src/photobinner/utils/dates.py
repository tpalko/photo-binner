import os
from datetime import datetime, timedelta
import re 
import logging 
from pytz import timezone
from utils.exifwrapper import ExifWrapper

logger = logging.getLogger(__name__)

UTC = timezone("UTC")
TZ = timezone(os.getenv('TZ', 'US/Eastern'))
EPOCH = datetime(1970, 1, 1)
UTC_EPOCH = UTC.localize(EPOCH)
LOCAL_EPOCH = UTC_EPOCH.astimezone(TZ)
DEFAULT_YEARS = [1970, 1980]

def _extract_date_from_path(filepath):
    path = filepath.rpartition('/')[0]
    date_matches = []
    date_matches.extend([ datetime.strptime(m, '%Y_%m_%d') for m in re.findall('[0-9]{4}_{1}[0-9]{2}_{1}[0-9]{2}', path) ])
    date_matches.extend([ datetime.strptime(m, '%Y-%m-%d') for m in re.findall('[0-9]{4}-{1}[0-9]{2}-{1}[0-9]{2}', path) ])
    date_matches.sort()
    logger.debug(" - dates from path: %s" % [ datetime.strftime(d, "%Y-%m-%d %H:%M:%S %z") for d in date_matches ])
    return TZ.localize(date_matches[0]) if len(date_matches) > 0 else None

def _extract_date_from_filename(filepath):
    logger.debug(" - trying to match timestamp from filename: %s" % filepath)
    match = re.search('[0-9]{8}[\_-]{1}[0-9]{6}', filepath)
    filename_date = None
    if match:
        logger.debug(" - filename timestamp: %s" % match.group())
        filename_timestamp = match.group()
        if filename_timestamp.find('_') > 0:
            filename_date = TZ.localize(datetime.strptime(filename_timestamp, "%Y%m%d_%H%M%S"))
        elif filename_timestamp.find('-') > 0:
            filename_date = TZ.localize(datetime.strptime(filename_timestamp, "%Y%m%d-%H%M%S"))
        else:
            logger.warn("- timestamp %s extracted from filename but datetime format not expected" % filename_timestamp)
        #calculated_timestamp = datetime.strftime(filename_date, "%Y-%m-%d %H:%M:%S")
        #calculated_date = datetime.strftime(filename_date, "%Y-%m-%d")
    else:
        logger.debug(" - no filename match for timestamp")
    return filename_date

def _date_match(d1, d2):
    return d1.year == d2.year and d1.month == d2.month and d1.day == d2.day

def _is_day_only(d):
    return d.hour == 0 and d.minute == 0 and d.second == 0

def get_target_date(working_path, original_path=None, run_stat_callback=None):
    '''
    1. get file stats 
    2. get localized file mtime -> target_date_from_stat 
    3. get file atime / mtime -> target_atime / target_mtime 
    4. extract date from filename -> target_date_from_filename
    5. extract date from path -> target_date_from_path
    6. get image metadata datetime -> target_date_from_exif
    '''

    if not original_path:
        original_path = working_path

    file_stats = os.stat(working_path)
    # -- this assumed file was read as UTC, which is was not
    #target_date = UTC.localize(datetime.fromtimestamp(file_stats.st_mtime)).astimezone(TZ)
    # -- call file stats in local time
    target_date_from_stat = TZ.localize(datetime.fromtimestamp(file_stats.st_mtime))
    target_atime = file_stats.st_atime
    target_mtime = file_stats.st_mtime

    target_date_from_filename = _extract_date_from_filename(original_path)

    target_date_from_path = _extract_date_from_path(original_path)

    ew = ExifWrapper(filepath=working_path)
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
    logger.debug(" - stat_date_as_utc: %s" % stat_date_as_utc)

    # -- if the stat date, which is timezone-aware, taken as UTC equals the exif date
    # -- then ...
    if target_date_from_exif and datetime.strftime(stat_date_as_utc, "%Y-%m-%d %H:%M") == datetime.strftime(target_date_from_exif, "%Y-%m-%d %H:%M"):
        logger.warn(" - file date is double timezoned")
        # - basically add back (once) the hours of the local offset - it was offset twice
        target_date_from_stat = target_date_from_stat + timedelta(hours=-target_date_from_stat.utcoffset().total_seconds()/(60*60))
        target_mtime = (target_date_from_stat - LOCAL_EPOCH).total_seconds()
        if run_stat_callback:
            run_stat_callback('anomalies', 'file-date-double-timezoned', original_path)

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
        if _is_day_only(target_dates[is_day_only]):
            for same_day in [ d for d in target_dates if d != is_day_only ]:
                if _date_match(target_dates[is_day_only], target_dates[same_day]) and not _is_day_only(target_dates[same_day]):
                    remove_sources.append(is_day_only)
                    logger.debug(" - excluding %s source as it has no time information and %s matches the date" % (is_day_only, same_day))
                    break
    target_dates = { d: target_dates[d] for d in target_dates if d not in remove_sources }

    # -- log the sorted list of candidates
    target_dates_log = [ { t: datetime.strftime(target_dates[t], "%Y-%m-%d %H:%M:%S %z") } for t in sorted(target_dates, key=lambda x: target_dates[x]) ]
    logger.debug(" - %s" % target_dates_log)

    # -- accounting for the possible one-second lag between metadata and inode information
    # -- if metadata is more recent, it suggests iPhone
    if target_date_from_exif and target_date_from_stat and (target_date_from_exif - target_date_from_stat).total_seconds() > 1:
        logger.warn(" - exif (%s) is newer than stat (%s) - iPhone?" % (datetime.strftime(target_date_from_exif, "%Y-%m-%d %H:%M:%S %z"), datetime.strftime(target_date_from_stat, "%Y-%m-%d %H:%M:%S %z")))
        if run_stat_callback:
            run_stat_callback('anomalies', 'recent-exif', original_path)

    # -- order to assign dates (highest priority is last!)
    date_source_priority = ['stat', 'path', 'filename', 'exif']

    target_date = None

    for date_source in [ d for d in date_source_priority if d in target_dates ]:
        if not target_date or (date_source == 'filename' or target_dates[date_source] < target_date):
            target_date = target_dates[date_source]
            target_date_assigned_from = date_source

    logger.info(" - target date assigned using %s: %s" % (target_date_assigned_from, datetime.strftime(target_date, "%Y-%m-%d %H:%M:%S %z")))
    if run_stat_callback:
        run_stat_callback('date_sources', target_date_assigned_from, original_path)

    if target_date.year in DEFAULT_YEARS:
        logger.warn(" - target date almost surely invalid (%s)" % (datetime.strftime(target_date, "%Y-%m-%d")))
        if run_stat_callback:
            run_stat_callback('anomalies', 'no-valid-date', original_path)

    # -- atime/mtime are by default what is already on the file
    # -- we want to avoid changing this unless it's completely wrong
    if target_date != target_date_from_stat:
        old_file_time = datetime.strftime(target_date_from_stat, "%Y-%m-%d %H:%M:%S %z")
        new_file_time = datetime.strftime(target_date, "%Y-%m-%d %H:%M:%S %z")
        logger.warn(" - file time incorrect: %s -> %s" % (old_file_time, new_file_time))
        target_timestamp = (target_date - LOCAL_EPOCH).total_seconds()
        #target_atime = target_timestamp
        target_mtime = target_timestamp

    logger.debug(" - atime: %s" % datetime.strftime(TZ.localize(datetime.fromtimestamp(target_atime)), "%Y-%m-%d %H:%M:%S %z"))
    logger.debug(" - mtime: %s" % datetime.strftime(TZ.localize(datetime.fromtimestamp(target_mtime)), "%Y-%m-%d %H:%M:%S %z"))

    new_filename = None

    # -- if we've extracted a date from the filename (not path) and that date is different than the settled date
    # -- we're going to rename the file to match
    # if target_date_from_filename and target_date and (target_date_from_filename - target_date).total_seconds() > 1:
    #     filename = original_path.rstrip('/').rpartition('/')[-1]
    #     file_prefix = filename.split('_')[0]
    #     file_suffix = filename.split('.')[-1]
    #     millisecond = datetime.strftime(target_date, "%f")[0:3]
    #     new_filename_stamp = datetime.strftime(target_date, "%Y%m%d_%H%M%S")
    #     new_filename = "%s_%s%s.%s" %(file_prefix, new_filename_stamp, millisecond, file_suffix)
    #     logger.warn(" - timestamp extracted from filename does not match calculated timestamp, renaming %s -> %s" % (filename, new_filename))
    #     if run_stat_callback:
    #         run_stat_callback('anomalies', 'filename-date-incorrect', original_path)

    # -- same deal as above but with the date found in the path, and we're just logging the fact, not renaming the folder
    if target_date_from_path and datetime.strftime(target_date_from_path, "%Y-%m-%d") != datetime.strftime(target_date, "%Y-%m-%d"):
        logger.warn(" - date extracted from path %s does not match calculated date %s" % (datetime.strftime(target_date_from_path, "%Y-%m-%d"), datetime.strftime(target_date, "%Y-%m-%d")))
        if run_stat_callback:
            run_stat_callback('anomalies', 'path-date-incorrect', original_path)

    return (target_date, target_atime, target_mtime, new_filename, target_date_assigned_from,)
