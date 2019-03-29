#!/usr/bin/python

import sys
from datetime import datetime, tzinfo, timedelta
import exifread
from pytz import timezone
import click
import logging
import json

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
        for k in kwargs:
            self.__setattr__(k, kwargs[k])
        self.tz = timezone(self.timezone)
        self.logger = logging.getLogger(__name__)
        self.logger.debug("OPTIONS -> TIMEZONE: %s" %(self.timezone))

    def _extract_metadata(self, key=None):
        values = {}
        value = None
        with open(self.filepath) as f:
            TAGS = exifread.process_file(f, details=False)
            if key:
                for tag in VALUE_MAP[key]:
                    if tag in TAGS and not value:
                        value = TAGS[tag]
            else:
                for key in VALUE_MAP:
                    for tag in VALUE_MAP[key]:
                        if tag in TAGS and key not in values:
                            values[key] = TAGS[tag]
        return value if value else values

    def _get_date_object(self, raw_image_datetime):
        local_image_datetime = None
        if raw_image_datetime:
            image_datetime = None
            try:
                # - the timestamp is UTC with no timezone markers
                image_datetime = datetime.strptime("%s" %(str(raw_image_datetime)), "%Y:%m:%d %H:%M:%S")
            except:
                _log_escrow(logging.WARN, " - failed to parse '%s'" % str(raw_image_datetime))
            if not image_datetime:
                try:
                    # - 2010:10:24 15:23: 2
                    image_datetime = datetime.strptime("%s" % (str(raw_image_datetime)), "%Y:%m:%d %H:%M: %S")
                except:
                    _log_escrow(logging.WARN, " - failed to parse '%s'" % str(raw_image_datetime))
            if image_datetime:
                if self.assume_local:
                    # - call it what it is
                    local_image_datetime = self.tz.localize(image_datetime)
                else:
                    # - call it what it is
                    utc_image_datetime = UTC.localize(image_datetime)
                    # - and then convert it
                    local_image_datetime = utc_image_datetime.astimezone(self.tz)
        return local_image_datetime

    def image_datetime(self):
        raw_image_datetime = self._extract_metadata(key='image_datetime')
        return self._get_date_object(raw_image_datetime)

    def all_values(self):
        all_values = self._extract_metadata()
        if 'image_datetime' in all_values:
            all_values['image_datetime'] = self._get_date_object(all_values['image_datetime'])
        return all_values

@click.command()
@click.option('--full', '-f', 'full', required=False, default=False, is_flag=True, help='Show full date w/ time and TZ offset')
#@click.option('--debug', '-d', 'debug', required=False, default=False, help='Show debug output')
@click.option('--timezone', '-t', 'timezone', required=False, default=DEFAULT_TIMEZONE, help='Override %s timezone' % DEFAULT_TIMEZONE)
@click.option('--assume-local/--assume-not-local', '-l', 'assume_local', required=False, default=True, help='Whether obtained timestamp is assumed to be in the set timezone')
@click.argument('filename')
def main(full, timezone, filename, assume_local):

    if not filename:
        exit(1)

    id = ExifWrapper(filepath=filename, timezone=timezone, assume_local=assume_local)

    timestamp = id.image_datetime()

    if full:
        print(datetime.strftime(timestamp, "%Y-%m-%d %H:%M:%S %z"))
    else:
        print(datetime.strftime(timestamp, "%Y-%m-%d %z"))

if __name__ == "__main__":
    main()
