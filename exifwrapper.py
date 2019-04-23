#!/usr/bin/python

import sys
from datetime import datetime, tzinfo, timedelta
import exifread
from pytz import timezone
import click
import logging
import json
import signal
from glob import glob
import os

# exifread_logger = logging.getLogger('exifread')
# exifread_logger.setLevel(logging.WARN)

UTC = timezone("UTC")
DEFAULT_TIMEZONE = 'US/Eastern'

VALUE_MAP = {
    'image_datetime': ['Image DateTime', 'EXIF DateTimeOriginal'],
    'image_make': ['Image Make'],
    'image_model': ['Image Model']
}

class ExifWrapper(object):

    timezone = DEFAULT_TIMEZONE
    assume_local = True
    filepath = None
    tz = None

    def __init__(self, *args, **kwargs):
        if 'filepath' not in kwargs:
            raise ValueError("ExifWrapper requires a 'filepath'")
        for k in kwargs:
            self.__setattr__(k, kwargs[k])
        self.tz = timezone(self.timezone)
        self.logger = logging.getLogger(__name__)
        self.logger.debug("OPTIONS -> TIMEZONE: %s" %(self.timezone))

    def _extract_all_metadata(self):
        '''
        Looks for all EXIF keys referenced in each key type in VALUE_MAP and returns a dict of the first value found for each type.
        '''
        values = {}
        with open(self.filepath) as f:
            TAGS = exifread.process_file(f, details=False)
            for key in VALUE_MAP:
                for tag in VALUE_MAP[key]:
                    if tag in TAGS and key not in values:
                        values[key] = TAGS[tag]
        return values

    def _extract_metadata_for_key(self, key=None):
        '''
        Looks for EXIF keys in VALUE_MAP of key type passed and returns the first one found.
        '''
        if not key:
            return self._extract_all_metadata()
        value = None
        with open(self.filepath) as f:
            TAGS = exifread.process_file(f, details=False)
            for tag in VALUE_MAP[key]:
                if tag in TAGS and not value:
                    value = TAGS[tag]
        return value if value else values

    def _fix_timezone(self, image_datetime):
        if self.assume_local:
            # - call it what it is
            return self.tz.localize(image_datetime)
        else:
            # - call it what it is
            utc_image_datetime = UTC.localize(image_datetime)
            # - and then convert it
            return utc_image_datetime.astimezone(self.tz)

    def _get_date_object(self, raw_image_datetime):
        if not raw_image_datetime:
            return None
        local_image_datetime = None
        attempt_formats = ["%Y:%m:%d %H:%M:%S", "%Y:%m:%d %H:%M: %S"]
        for format in attempt_formats:
            try:
                # - the timestamp is UTC with no timezone markers
                image_datetime = datetime.strptime("%s" %(str(raw_image_datetime)), format)
                local_image_datetime = self._fix_timezone(image_datetime)
                break
            except:
                pass

        return local_image_datetime

    def image_datetime(self):
        '''
        Returns DateTime of first 'image datetime' type EXIF key
        '''
        raw_image_datetime = self._extract_metadata_for_key(key='image_datetime')
        return self._get_date_object(raw_image_datetime)

    def all_values(self):
        '''
        Returns dict of first-found of each configured EXIF key type
        '''
        all_values = self._extract_all_metadata()
        if 'image_datetime' in all_values:
            all_values['image_datetime'] = self._get_date_object(all_values['image_datetime'])
        return all_values

    def exif_key_gen(self):
        path = self.filepath
        if os.path.isdir(path):
            path = glob("%s/*" % path)[0]
        with open(path) as f:
            TAGS = exifread.process_file(f, details=False)
            for i, key in enumerate(TAGS):
                yield (i, key, TAGS[key])

    exif_keymap = {}
    def show_exif_keys(self):
        for i, key, _ in self.exif_key_gen():
            self.exif_keymap[i+1] = key
            print("%s: %s" % (i+1, key))
        print("Which key? ")
        key_number = input()
        self.read_exif_key(self.exif_keymap[key_number])

    def read_exif_key(self, key):
        if os.path.isdir(self.filepath):
            print("%s:" % key)
            for path in glob("%s/*" % self.filepath):
                with open(path) as f:
                    TAGS = exifread.process_file(f, details=False)
                    print("%s: %s" % (path, TAGS[key]))
        else:
            with open(self.filepath) as f:
                TAGS = exifread.process_file(f, details=False)
                print("%s: %s" % (key, TAGS[key]))

alive = True
def sigint_handler(sig, frame):
    global alive
    alive = False
    print("Press Ctrl-C again to exit..")

@click.command()
@click.option('--full', '-f', 'full', required=False, default=False, is_flag=True, help='Show full date w/ time and TZ offset')
#@click.option('--debug', '-d', 'debug', required=False, default=False, help='Show debug output')
@click.option('--timezone', '-t', 'timezone', required=False, default=DEFAULT_TIMEZONE, help='Override %s timezone' % DEFAULT_TIMEZONE)
@click.option('--assume-local/--assume-not-local', '-l', 'assume_local', required=False, default=True, help='Whether obtained timestamp is assumed to be in the set timezone')
@click.argument('filepath')
def main(full, timezone, filepath, assume_local):

    if not filepath:
        exit(1)

    wrap = ExifWrapper(filepath=filepath, timezone=timezone, assume_local=assume_local)
    signal.signal(signal.SIGINT, sigint_handler)

    command_map = {
        "1": { 'f': wrap.show_exif_keys, 'm': "Show EXIF Keys" }
    }

    while(alive):
        for i in command_map.keys():
            print("%s) %s" % (i, command_map[i]['m']))
        try:
            command = input()
            command_map[str(command)]['f']()
        except SyntaxError as se:
            if not str(sys.exc_info()[1]).startswith('unexpected EOF'):
                print(sys.exc_info())
        except:
            print(sys.exc_info())

if __name__ == "__main__":
    main()
