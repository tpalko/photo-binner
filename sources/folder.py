import os
import sys
import subprocess
import logging
sys.path.append("..")
from source import Source

logger = logging.getLogger(__name__)

def classdef():
    return Folder

class Folder(Source):

    def verify(self, mask="*", from_date=None):
        return self._is_not_empty(mask)

    def paths(self, mask="*", from_date=None):
        return self._paths(mask)
