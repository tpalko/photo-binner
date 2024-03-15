import os
import sys
import subprocess
import logging
from plugin.source import Source, SourceFile, StitchFolder

logger = logging.getLogger(__name__)

class SingleFile(Source):

    def sigint_handler(self):
        return self._sigint_handler()

    def verify(self):
        return self._is_not_empty()

    def paths(self):
        yield SourceFile(self.mountpoint)
