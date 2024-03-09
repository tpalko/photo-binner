#!/usr/bin/python

import logging

class LogEscrow(logging.Logger):

    # - log escrow
    # - central log function that accepts a log statement with an event or trigger and
    # - 1) (if event) stores statement in escrow with the event, which when triggered logs the statement
    # - 2) logs the statement immediately, normally
    # - 3) (if trigger) finds escrowed statements with a matching event, logs those, and then logs the statement


    def __init__(self, *args, **kwargs):
        self.logger = logging.getLogger(kwargs['name'])
        self.log_escrow = {}

    def _log_align(self, level, statement):
        longest_log_level_name = 'warning'
        self.logger.log(level, "%*s%s" % (len(longest_log_level_name)-len(logging.getLevelName(level)), "", statement))
        #self.logger.log(level, "{:>26}".format(statement))

    def clear_log_escrow(self):
        self.log_escrow = {}

    def release_log_escrow(self, level=logging.NOTSET, trigger=None):
        if level > logging.NOTSET:
            level_holds = [ s for e in self.log_escrow for s in self.log_escrow[e] if s['level'] <= level ]
            for s in level_holds:
                self._log_align(s['level'], s['statement'])
            self.log_escrow = { e: [ s for s in self.log_escrow[e] if s['level'] > level ] for e in self.log_escrow }
        if trigger and trigger in self.log_escrow:
            for s in self.log_escrow[trigger]:
                self._log_align(s['level'], s['statement'])
            del self.log_escrow[trigger]

    def debug(self, statement=None, event=None):
        self._log_escrow(level=logging.DEBUG, statement=statement, event=event)

    def info(self, statement=None, event=None):
        self._log_escrow(level=logging.INFO, statement=statement, event=event)

    def warn(self, statement=None, event=None):
        self._log_escrow(level=logging.WARN, statement=statement, event=event)

    def error(self, statement=None, event=None):
        self._log_escrow(level=logging.ERROR, statement=statement, event=event)

    def fatal(self, statement=None, event=None):
        self._log_escrow(level=logging.FATAL, statement=statement, event=event)

    def _log_escrow(self, level=logging.INFO, statement=None, event=None):
        if event:
            if event not in self.log_escrow:
                self.log_escrow[event] = []
            self.log_escrow[event].append({'level': level, 'statement': statement})
        else:
            self.release_log_escrow(level=level)
            self._log_align(level, statement)
