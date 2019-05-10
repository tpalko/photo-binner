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

DEFAULT_MASK = "*"

class Source():

    __metaclass__ = ABCMeta

    name = None
    mountpoint = None
    exclude_descriptive = None
    transfer_method = None
    filename_mask = "*.mp4"
    from_date = None
    mask = DEFAULT_MASK
    processed_files = []

    def __init__(self, *args, **kwargs):
        for k in kwargs:
            self.__setattr__(k, kwargs[k])
        self.logger = logging.getLogger(__name__)

    @abstractmethod
    def verify(self):
        pass

    @abstractmethod
    def paths(self):
        pass

    @abstractmethod
    def sigint_handler(self):
        pass

    def _filter_media_files(self, filenames):
        return [ f for f in filenames if f[0:2] != "._" and (f[-3:].lower() in ("jpg", "gif", "png", "raw", "mov", "crw", "cr2", "avi", "mp4", "bmp", "psd") or f[-4:] in ("tiff")) ]

    def _filter_video_files(self, filenames):
        return [ f for f in filenames if f[0:2] != "._" and f[-3:].lower() in ("mov", "avi", "mp4") ]

    def _filter_mask(self, filenames):
        return [ f for f in filenames if f[0:2] != "._" and f[-3:].lower() in ("mov", "avi", "mp4") ]

    def _filter(self, filenames):
        if self.mask == DEFAULT_MASK:
            self.logger.debug("Filtering for media files only..")
            return self._filter_media_files(filenames)
        else:
            self.logger.debug("Applying mask '%s'" % self.mask)
            filenames = [ f for f in filenames if re.match(self.mask, f) ]

    def _is_not_empty(self):
        self.logger.debug("Checking if not empty: %s" % self.mountpoint)
        notempty = False
        if not os.path.exists(self.mountpoint):
            self.logger.warn("Supplied path '%s' does not exist" % self.mountpoint)
        elif os.path.isfile(self.mountpoint):
            notempty = True
            self.logger.debug(" - this file exists")
        else:
            for (current_folder, dirnames, filenames) in os.walk(self.mountpoint, topdown=True):
                filenames = self._filter(filenames)
                self.logger.debug(" - %s: %s files" % (current_folder, len(filenames)))
                if len(filenames) > 0:
                    notempty = True
                    break
        return notempty

    def _is_processed(self, filepath):
        return filepath in self.processed_files

    def _paths(self):
        self.logger.debug("Walking %s.." % self.mountpoint)
        self.logger.debug("Excluding folders: %s" % FIX_EXCLUDES)
        for (current_folder, dirnames, filenames) in os.walk(self.mountpoint, topdown=True):
            dirnames[:] = [ d for d in dirnames if os.path.abspath(d) not in FIX_EXCLUDES ]
            image_files = self._filter(filenames)
            for filename in image_files:
                filepath = os.path.join(current_folder, filename)
                if self._is_processed(filepath):
                    self.logger.debug(" - found as processed, skipping..")
                    continue
                yield filepath

    def _sigint_handler(self, callback=None):
        def handler(sig, frame):
            if callback:
                callback()
        return handler
