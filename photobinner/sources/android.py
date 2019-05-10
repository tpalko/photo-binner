import os
import sys
import subprocess
import logging
from datetime import datetime
from photobinner.source import Source

ADB_KEY_PATH = '~tpalko/.android/adbkey'

ANDROID_PATHS = [
    "/mnt/sdcard/DCIM/baconreader",
    "/mnt/sdcard/DCIM/Camera", # jpg
    "/mnt/sdcard/DCIM/Google Photos", #jpg
    "/mnt/sdcard/Download", # any
    "/mnt/sdcard/panoramas",
    "/mnt/sdcard/Pictures/baconreader", # jpg (any?)
    "/mnt/sdcard/Pictures/Image Editor", # png
    "/mnt/sdcard/Pictures/Image Editor/Downloads", # jpg (any?)
    "/mnt/sdcard/Pictures/Screenshots", # png
]

logger = logging.getLogger(__name__)

def classdef():
    return Android

class Android(Source):

    device = None

    def sigint_handler(self):
        return self._sigint_handler()

    def verify(self):
        import os.path as op

        from adb import adb_commands
        from adb import sign_m2crypto

        # KitKat+ devices require authentication
        signer = sign_m2crypto.M2CryptoSigner(op.expanduser(ADB_KEY_PATH))
        # Connect to the device
        self.device = adb_commands.AdbCommands()
        try:
            kill_server_cmd = ['adb', 'kill-server']
            adb_kill_server = subprocess.Popen(kill_server_cmd)
            logger.info(" -> %s" % kill_server_cmd)
            (kill_server_out, kill_server_err,) = adb_kill_server.communicate(None)
            if kill_server_out:
                logger.info(kill_server_out)
            if kill_server_err:
                logger.error(kill_server_err)
            logger.info("Attempting device connection..")
            self.device.ConnectDevice(rsa_keys=[signer])
            logger.info("Examining filepaths..")
            self.files = {}
            any_files = False
            ctime_filter = ''
            if self.from_date:
                delta = datetime.now() - self.from_date
                ctime_filter = ' -ctime -%s' % delta.days
            for path in ANDROID_PATHS:
                #  -name \"%s\"
                cmd_find = 'find \"%s\" -type f%s' % (path, ctime_filter)
                logger.info("Getting contents of %s: \"%s\"" % (path, cmd_find))
                raw_files = self.device.Shell(cmd_find)
                filtered_files = self._filter(raw_files.split('\n'))
                if len(filtered_files) > 0:
                    self.files[path] = filtered_files
                    any_files = True
            return any_files
        except:
            logger.error(sys.exc_info())
        return False

    def paths(self):
        for path in self.files:
            for filepath in self.files[path]:
                logger.debug(" - have file %s" % filepath)
                if self._is_processed(filepath):
                    logger.warn("%s found as processed, skipping.." % filepath)
                    continue
                filename = filepath.rpartition('/')[-1]
                if filename.strip() == '':
                    continue
                size_bytes = int(self.device.Shell("stat \"%s\" | grep Size | cut -d \" \" -f 4" % filepath))
                mb_contents = size_bytes*1.0/(1024*1024)
                logger.debug(" - have %.2f MB contents" % mb_contents)
                targetfilepath = os.path.join('/tmp', filename)
                # ps = subprocess.Popen(['touch', targetfilepath])
                # (touchout, toucherr,) = ps.communicate(None)
                # if touchout:
                #     logger.info(touchout)
                # if toucherr:
                #     logger.info(toucherr)
                logger.debug(" - attempting to open for writing %s" % targetfilepath)
                with open(targetfilepath, 'wb') as targetfile:
                    logger.debug(" - attempting to pull %s -> %s" % (filepath, targetfilepath))
                    targetfile.write(self.device.Pull(filepath))
                # -- convention is to yield the original filepath and the modified/accessible filepath (if modified)
                yield (filepath, targetfilepath)
                logger.warn("Deleting %s.." % targetfilepath)
                if os.path.exists(targetfilepath):
                    os.remove(targetfilepath)
