#!/usr/bin/env python3

from sources.android import Android

config = {
  'ip_address': '192.168.1.37',
  'adb_key_path': '/home/debian/tpalko/.android/adbkey'
}

a = Android(**config)
a.test()
