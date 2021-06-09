import os
import sys
import subprocess
import logging
from photobinner.sources.source import Source, SourceFile, StitchFolder

logger = logging.getLogger(__name__)

class Folder(Source):

    def sigint_handler(self):
        return self._sigint_handler()

    def verify(self):
        return self._is_not_empty()

    def paths(self):
        for filepath in self._paths():
            # -- convention is to yield the original filepath and the modified/accessible filepath (if modified)
            yield SourceFile(filepath)
        logger.info("Now processing stitch folders (BlockDevice)..")
        for stitch_folder in self._stitch_folders():
            yield StitchFolder(stitch_folder)
