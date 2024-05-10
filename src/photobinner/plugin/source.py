import os
import sys
import subprocess
import logging
import re
from abc import ABCMeta, abstractmethod
from utils.common import md5

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

class SourceFile():

    original_path = None
    working_path = None
    md5 = None 
    size_kb = None 

    def __init__(self, *args, **kwargs):
        self.original_path = args[0]
        self.working_path = args[1] if len(args) > 1 else self.original_path
        self.md5 = md5(self.working_path)
        file_stats = os.stat(self.working_path)
        self.size_kb = float(file_stats.st_size) / 1024

class StitchFolder(SourceFile):
    pass

class Source():

    __metaclass__ = ABCMeta

    name = None
    mountpoint = None
    target = None
    exclude_descriptive = None
    transfer_method = None
    filename_mask = "*.mp4"
    from_date = None
    mask = DEFAULT_MASK
    processed_files = []
    stitch_folder_match = "^STITCH_[0-9]+$"
    stitch_folders = []

    def __init__(self, *args, **kwargs):
        logging.basicConfig(level=logging.DEBUG)
        self.logger = logging.getLogger(__name__)
        for k in kwargs:
            val = kwargs[k]
	    # -- this is a list-as-string we should parse 
            if type(kwargs[k]) == str and kwargs[k].count(",") > 0:
                val = kwargs[k].split(',')
            self.__setattr__(k, val)
            self.logger.debug(" - set attribute %s: %s" % (k, val))

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
        return [ f for f in filenames if f[0:2] != "._" and (f[-3:].lower() in ("jpg", "gif", "png", "raw", "mov", "crw", "cr2", "avi", "mp3", "mp4", "bmp", "psd") or f[-4:] in ("tiff")) ]

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
        # if not os.path.exists(self.mountpoint):
        #     self.logger.warn("Supplied path '%s' does not exist" % self.mountpoint)
        if os.path.isfile(self.mountpoint):
            notempty = True
            self.logger.debug(" - source exists as a file")
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
            self.stitch_folders.extend([ os.path.join(self.mountpoint, d) for d in dirnames if re.search(self.stitch_folder_match, d) ])
            self.logger.info(" - %s stitch folders found: %s" % (len(self.stitch_folders), ",".join(self.stitch_folders)))
            dirnames[:] = [ d for d in dirnames if os.path.abspath(d) not in FIX_EXCLUDES and not re.search(self.stitch_folder_match, d) ]
            image_files = self._filter(filenames)
            for filename in image_files:
                filepath = os.path.join(current_folder, filename)
                # if self._is_processed(filepath):
                #     self.logger.info(" - %s found as processed, skipping.." % filepath)
                #     continue
                yield filepath

    def _stitch_folders(self):
        self.logger.info("Now processing stitch folders (Source)..")
        for stitch_folder in self.stitch_folders:
            yield stitch_folder

    def _sigint_handler(self, callback=None):
        def handler(sig, frame):
            if callback:
                callback()
        return handler
