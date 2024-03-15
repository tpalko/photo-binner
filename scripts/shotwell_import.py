#!/usr/bin/python

import os
import re
import json

def run():
    zerofiles = {}
    for (folder, dirnames, filenames) in os.walk('/media/floor/pics/inbox'):
        for filename in filenames:
            filepath = os.path.join(folder, filename)
            stats = os.stat(filepath)
            if stats.st_size == 0:
                search = re.search("IMG_[0-9]+", filename)
                if search:
                    zerofiles[search.group()] = filepath
    found_zerofiles = {}
    for (folder, dirnames, filenames) in os.walk('/media/floor/pics', topdown=True):
        dirnames[:] = [ d for d in dirnames if not d.endswith('/inbox') ]
        for filename in filenames:
            search = re.search("^IMG_[0-9]+", filename)
            if search:
                if search.group() in zerofiles:
                    if folder not in found_zerofiles:
                        found_zerofiles[folder] = []
                    found_zerofiles[folder].append(filename)
    print(json.dumps(found_zerofiles))

if __name__ == "__main__":
    run()
