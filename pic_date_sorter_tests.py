#!/usr/bin/python

import unittest
from exifwrapper import ExifWrapper
from datetime import datetime
from pytz import timezone
from pic_date_sorter import _get_target_date, _extract_date_from_path, _extract_date_from_filename
import os

TZ = timezone('US/Eastern')

class TestPicDateSorter(unittest.TestCase):

    def test_get_target_date(self):
        current_path = '/media/storage/pics/2010/99 Point View Parkway/2010_11_28/CRW_9939_CRW_embedded_2.jpg'
        (target_date, target_atime, target_mtime, new_filename, target_date_assigned_from,) = _get_target_date(self.current_path)

    def test_date_from_stat(self):
        file_stats = os.stat(self.current_path)
        # -- this assumed file was read as UTC, which is was not
        #target_date = UTC.localize(datetime.fromtimestamp(file_stats.st_mtime)).astimezone(TZ)
        # -- call file stats in local time
        target_date_from_stat = TZ.localize(datetime.fromtimestamp(file_stats.st_mtime))
        self.assertEqual(target_date_from_stat, TZ.localize(datetime.strptime('2018-01-01', '%Y-%m-%d')))

    def test_date_from_filename(self):
        target_date_from_filename = _extract_date_from_filename(self.current_path)
        self.assertEqual(target_date_from_filename, TZ.localize(datetime.strptime('2018-01-01', '%Y-%m-%d')))

    def test_date_from_path(self):
        target_date_from_path = _extract_date_from_path(self.current_path)
        self.assertEqual(target_date_from_path, TZ.localize(datetime.strptime('2018-01-01', '%Y-%m-%d')))

    def test_date_from_exif(self):
        ew = ExifWrapper(filepath=self.current_path)
        target_date_from_exif = ew.image_datetime()
        self.assertEqual(target_date_from_exif, TZ.localize(datetime.strptime('2018-01-01', '%Y-%m-%d')))

if __name__ == '__main__':
    unittest.main()
