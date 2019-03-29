import os
import sys
import subprocess
import logging
from datetime import datetime
sys.path.append("..")
from source import Source

ADB_KEY_PATH = '~tpalko/.android/adbkey'

ANDROID_PATHS = [
    "/mnt/sdcard/DCIM/Camera",
    "/mnt/sdcard/DCIM/baconreader",
    "/mnt/sdcard/Download",
    "/sdcard/Pictures/Screenshots",
    "/sdcard/Pictures/Image Editor",
    "/sdcard/Pictures/Image Editor/Downloads",
    "sdcard/panoramas"
]

logger = logging.getLogger(__name__)

def classdef():
    return Android

class Android(Source):

    device = None

    def verify(self, mask="*", from_date=None):
        import os.path as op

        from adb import adb_commands
        from adb import sign_m2crypto

        # KitKat+ devices require authentication
        signer = sign_m2crypto.M2CryptoSigner(op.expanduser(ADB_KEY_PATH))
        # Connect to the device
        self.device = adb_commands.AdbCommands()
        try:
            logger.info("Attempting device connection..")
            self.device.ConnectDevice(rsa_keys=[signer])
            logger.info("Examining filepaths..")
            self.files = {}
            any_files = False
            ctime_filter = ''
            if from_date:
                delta = datetime.now() - from_date
                ctime_filter = ' -ctime -%s' % delta.days
            for path in ANDROID_PATHS:
                #  -name \"%s\"
                cmd_find = 'find \"%s\" -type f%s' % (path, ctime_filter)
                logger.info("Getting contents of %s: \"%s\"" % (path, cmd_find))
                raw_files = self.device.Shell(cmd_find)
                filtered_files = self._filter(raw_files.split('\n'), mask)
                if len(filtered_files) > 0:
                    self.files[path] = filtered_files
                    any_files = True
            return any_files
        except:
            logger.error(sys.exc_info())
        return False

    def paths(self, mask="*", from_date=None):
        for path in self.files:
            for filepath in self.files[path]:
                logger.debug(" - have file %s" % filepath)
                filename = filepath.rpartition('/')[-1]
                if filename.strip() == '':
                    continue
                targetfilepath = os.path.join('/tmp', filename)
                # ps = subprocess.Popen(['touch', targetfilepath])
                # (touchout, toucherr,) = ps.communicate(None)
                # if touchout:
                #     logger.info(touchout)
                # if toucherr:
                #     logger.info(toucherr)
                logger.debug(" - attempting to open for writing %s" % targetfilepath)
                with open(targetfilepath, 'wb') as targetfile:
                    logger.debug(" - attemtping to pull %s -> %s" % (filepath, targetfilepath))
                    filecontents = self.device.Pull(filepath) #, dest_file=targetfile) #dest_file=f)
                    len_contents = len(filecontents)
                    mb_contents = len_contents*1.0/(1024*1024)
                    logger.debug(" - have %.2f MB contents" % mb_contents)
                    targetfile.write(filecontents)
                yield targetfilepath
                #os.remove(targetfilepath)
