#!/usr/bin/env python3

import threading

# Implementation based on a StackOverflow answer by @NPE:
# https://stackoverflow.com/a/26586865/656767

class BlockingDict:
    def __init__(self):
        self._data = {}
        self._cv = threading.Condition()

    # Implements "bd[key]" (blocking, no timeout)
    def __getitem__(self, key):
        return self.get(key)

    # Implements "bd[key] = value"
    def __setitem__(self, key, value):
        self.put(key, value)

    # Implements "del bd[key]"
    def __delitem__(self, key):
        with self._cv:
            del self._data[key]

    def put(self, key, value):
        with self._cv:
            self._data[key] = value
            self._cv.notify_all()

    def get(self, key, default=None, *, timeout=None):
        with self._cv:
            self._cv.wait_for(lambda: key in self._data, timeout=timeout)
            # This will return default if timed out
            return self._data.get(key, default)
