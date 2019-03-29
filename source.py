import os
import sys
import subprocess
import logging
import re
from abc import ABCMeta, abstractmethod

# - some pics/ folders are outside the purview of sorting/fixing scripts
FIX_EXCLUDES = [
    '/media/storage/pics/LP',
    '/media/storage/pics/Scrabble',
    '/media/storage/pics/taty_pix',
    '/media/storage/pics/to_be_sorted',
    '/media/storage/pics/wallpaper',
    '/media/storage/pics/working',
    '/media/storage/pics/comics',
    '/media/storage/pics/Burn Folder.fpbf',
    '/media/storage/pics/Albums',
    '/media/storage/pics/inbox/exact_matches'
]

class Source():

    __metaclass__ = ABCMeta

    mountpoint = None
    exclude_descriptive = None
    transfer_method = None
    filename_mask = "*.mp4"

    def __init__(self, *args, **kwargs):
        for k in kwargs:
            self.__setattr__(k, kwargs[k])
        self.logger = logging.getLogger(__name__)

    @abstractmethod
    def verify(self, mask="*", from_date=None):
        pass

    @abstractmethod
    def paths(self, mask="*", from_date=None):
        pass

    def _filter_media_files(self, filenames):
        return [ f for f in filenames if f[0:2] != "._" and (f[-3:].lower() in ("jpg", "gif", "png", "raw", "mov", "crw", "cr2", "avi", "mp4", "bmp", "psd") or f[-4:] in ("tiff")) ]

    def _filter_video_files(self, filenames):
        return [ f for f in filenames if f[0:2] != "._" and f[-3:].lower() in ("mov", "avi", "mp4") ]

    def _filter_mask(self, filenames):
        return [ f for f in filenames if f[0:2] != "._" and f[-3:].lower() in ("mov", "avi", "mp4") ]

    def _filter(self, filenames, mask):
        if mask != "*":
            self.logger.debug("Applying mask '%s'" % mask)
            filenames = [ f for f in filenames if re.match(mask, f) ]
        else:
            self.logger.debug("Filtering for media files only..")
            return self._filter_media_files(filenames)

    def _is_not_empty(self, mask):
        self.logger.info("Checking if not empty..")
        notempty = False
        for (current_folder, dirnames, filenames) in os.walk(self.mountpoint, topdown=True):
            self.logger.info(" - %s" % current_folder)
            filenames = self._filter(filenames, mask)
            if len(filenames) > 0:
                notempty = True
                self.logger.info(" - not empty: %s files" % len(filenames))
                break
        return notempty

    def _paths(self, mask="*"):
        self.logger.info("Walking %s.." % self.mountpoint)
        self.logger.info("Excluding folders: %s" % FIX_EXCLUDES)
        for (current_folder, dirnames, filenames) in os.walk(self.mountpoint, topdown=True):
            dirnames[:] = [ d for d in dirnames if os.path.abspath(d) not in FIX_EXCLUDES ]
            image_files = self._filter(filenames, mask)
            for filename in image_files:
                yield os.path.join(current_folder, filename)


# class Source(object):
#
#     uuid = None
#     block_label = None
#     mountpoint = None
#     exclude_descriptive = None
#     transfer_method = None
#     platform = None
#     path_getters = {}
#     verify_action = {}
#     device = None
#
#     def __init__(self, *args, **kwargs):
#         for k in kwargs:
#             self.__setattr__(k, kwargs[k])
#         self.path_getters = {
#             PLATFORM_BLOCK: self.block_paths,
#             PLATFORM_ANDROID: self.android_paths
#         }
#         self.verify_action = {
#             PLATFORM_BLOCK: self.verify_block_device,
#             PLATFORM_ANDROID: self.verify_android
#         }
#
#     def android_paths(self):
#         files = {}
#         self._attempt_mount()
#         for source in ANDROID_PATHS:
#             logger.info("Getting contents of %s" % source)
#             files[source] = self.device.Shell('find \"%s\" -type f' % source)
#             for sourcefilepath in files[source].split('\n'):
#                 logger.debug(" - have file %s" % sourcefilepath)
#                 sourcefile = sourcefilepath.rpartition('/')[-1]
#                 targetfilepath = os.path.join('/tmp', sourcefile)
#                 # ps = subprocess.Popen(['touch', targetfilepath])
#                 # (touchout, toucherr,) = ps.communicate(None)
#                 # if touchout:
#                 #     logger.info(touchout)
#                 # if toucherr:
#                 #     logger.info(toucherr)
#                 logger.debug(" - attempting to open for writing %s" % targetfilepath)
#                 with open(targetfilepath, 'wb') as targetfile:
#                     logger.debug(" - attemtping to pull %s -> %s" % (sourcefilepath, targetfilepath))
#                     filecontents = self.device.Pull(sourcefilepath) #, dest_file=targetfile) #dest_file=f)
#                     targetfile.write(filecontents)
#                 yield targetfilepath
#                 os.remove(targetfilepath)
#         self._attempt_umount()
#
#     def block_paths(self):
#         for (current_folder, dirnames, filenames) in os.walk(self.mountpoint, topdown=True):
#             pre = dirnames
#             dirnames[:] = [ d for d in dirnames if os.path.abspath(d) not in FIX_EXCLUDES ]
#             post = dirnames
#             removed = len(pre) - len(post)
#             if removed > 0:
#                 _log_escrow(logging.WARN, "Removed %s excluded folders" % removed)
#
#             '''
#             /pics/2016/2016-07-21/.. files
#             /pics/some_event/.. files
#             /pics/2016/some_other_event/.. files
#             /pics/some_category/some_event/.. files
#             /pics/some_category/another_event/.. files
#
#             if parent folder is not the standard date folder
#             recreate the whole parent folder hierarchy by name in the year folder
#             '''
#
#             # if os.path.abspath(current_folder) in FIX_EXCLUDES:
#             #     _log_escrow(logging.INFO, "%s (skipping excluded folder)" % current_folder)
#             #     continue
#
#             image_files = [ f for f in filenames if f[0:2] != "._" and (f[-3:].lower() in ("jpg", "gif", "png", "raw", "mov", "crw", "cr2", "avi", "mp4", "bmp", "psd") or f[-4:] in ("tiff")) ]
#
#             for filename in image_files:
#                 yield os.path.join(current_folder, filename)
#
#     def get_paths(self):
#         return self.path_getters[self.platform]()
#
#     def _check_attached_device(self):
#         uuid = None
#         ps_blkid = subprocess.Popen(['blkid'], stdout=subprocess.PIPE)
#         ps_grepblkid = subprocess.Popen(['grep', self.block_label], stdin=ps_blkid.stdout, stdout=subprocess.PIPE)
#         (blkout, blkerr) = ps_grepblkid.communicate(None)
#         if blkout and len(blkout.strip()) > 0:
#             uuid = blkout.split(' ')[2].split('=')[1].strip('"')
#         else:
#             logger.info("Ain't got no device attached!")
#         return uuid
#
#     def _check_mountpoint(self, mountpoint):
#         if os.path.exists(mountpoint):
#             logger.info("Device appears to be attached and mounted!")
#             return True
#         else:
#             logger.info("Device is attached, but it ain't mounted!")
#             return False
#
#     def _check_mountpoint_folder(self, mountpoint):
#         if not os.path.isdir(mountpoint):
#             logger.info("Creating mount folder..")
#             os.makedirs(mountpoint)
#
#     def _attempt_mount(self):
#         ps_mount = subprocess.Popen(['mount', 'UUID=%s' % self.uuid, self.mountpoint])
#         logger.info("Attempting to mount device..")
#         (mountout, mounterr) = ps_mount.communicate(None)
#         if mounterr:
#             logger.error(mounterr)
#             return False
#         if mountout:
#             logger.debug(mountout)
#         return True
#
#     def _attempt_umount(self):
#         ps_umount = subprocess.Popen(['umount', self.mountpoint])
#         logger.info("Attempting to umount device..")
#         (umountout, umounterr) = ps_umount.communicate(None)
#         if umounterr:
#             logger.error(umounterr)
#             return False
#         if umountout:
#             logger.debug(umountout)
#         return True
#
#     def verify_block_device(self):
#         mounted = False
#         self.uuid = self._check_attached_device()
#         if self.uuid:
#             mount_attempts = 0
#             MAX_ATTEMPTS = 3
#             mounted = self._check_mountpoint(os.path.join(self.mountpoint, BLOCK_MOUNT_VERIFICATION_SUBFOLDER))
#             while not mounted:
#                 self._check_mountpoint_folder(self.mountpoint)
#                 self._attempt_mount()
#                 mounted = self._check_mountpoint(os.path.join(self.mountpoint, BLOCK_MOUNT_VERIFICATION_SUBFOLDER))
#                 if not mounted:
#                     mount_attempts += 1
#                     if mount_attempts >= MAX_ATTEMPTS:
#                         break
#                     os.sleep(3)
#         notempty = False
#         if mounted:
#             for (current_folder, dirnames, filenames) in os.walk(self.mountpoint, topdown=True):
#                 image_files = [ f for f in filenames if f[0:2] != "._" and (f[-3:].lower() in ("jpg", "gif", "png", "raw", "mov", "crw", "cr2", "avi", "mp4", "bmp", "psd") or f[-4:] in ("tiff")) ]
#                 if len(image_files) > 0:
#                     notempty = True
#                     break
#             self._attempt_umount()
#         return notempty
#
#     def verify_android(self):
#         import os.path as op
#
#         from adb import adb_commands
#         from adb import sign_m2crypto
#
#         # KitKat+ devices require authentication
#         signer = sign_m2crypto.M2CryptoSigner(op.expanduser(ADB_KEY_PATH))
#         # Connect to the device
#         self.device = adb_commands.AdbCommands()
#         try:
#             self.device.ConnectDevice(rsa_keys=[signer])
#             return True
#         except:
#             logger.error(sys.exc_info())
#         return False
#
#     def verify(self):
#         return self.verify_action[self.platform]()
