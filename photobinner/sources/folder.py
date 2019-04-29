import os
import sys
import subprocess
import logging
from photobinner.source import Source

logger = logging.getLogger(__name__)

def classdef():
    return Folder

class Folder(Source):

    def sigint_handler(self):
        def handler(sig, frame):
            pass
        return handler

    def verify(self):
        return self._is_not_empty()

    def paths(self):
        return self._paths()
