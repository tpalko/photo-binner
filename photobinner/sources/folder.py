import os
import sys
import subprocess
import logging
from photobinner.source import Source, SourceFile

logger = logging.getLogger(__name__)

def classdef():
    return Folder

class Folder(Source):

    def sigint_handler(self):
        return self._sigint_handler()

    def verify(self):
        return self._is_not_empty()

    def paths(self):
        for filepath in self._paths():
            # -- convention is to yield the original filepath and the modified/accessible filepath (if modified)
            yield SourceFile(filepath)
