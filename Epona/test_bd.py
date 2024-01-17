#!/usr/bin/env python3

import sys
import os.path
sys.path.insert(0, os.path.dirname(os.path.abspath(sys.argv[0])))

from blockingdict import BlockingDict
from threading import Thread
import time

import unittest
import unittest.mock as mock


class BlockTimer:
    def __enter__(self):
        self.start = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.elapsed = time.perf_counter() - self.start


class A0_BlockingDictTest(unittest.TestCase):
    def setUp(self):
        self.bd = BlockingDict()

    def test_01_put_get(self):
        self.bd.put(3, 8)
        self.assertEqual(self.bd.get(3), 8)

    def test_02_get_not_present(self):
        self.assertEqual(self.bd.get(5, timeout=0), None)

    def test_03_get_not_present_default(self):
        self.assertEqual(self.bd.get(5, 18, timeout=0), 18)

    def test_04_get_not_present_timeout(self):
        # Hopefully 1ms is long enough to differentiate
        with BlockTimer() as t:
            self.bd.get(5, timeout=0.001)
        self.assertGreaterEqual(t.elapsed, 0.001)

    def test_05_blocking(self):
        def helper():
            time.sleep(0.001)
            self.bd.put(15, -2)

        thr = Thread(target=helper)

        with BlockTimer() as t:
            thr.start()
            res = self.bd.get(15, timeout=0.002)
        thr.join()

        self.assertEqual(res, -2)
        # Blocked until the value was added
        self.assertGreaterEqual(t.elapsed, 0.001)
        # Unblocked as soon as the value was added
        self.assertLess(t.elapsed, 0.002)

    def test_06_blocking_other_added(self):
        def helper():
            time.sleep(0.001)
            self.bd.put(14, -2)

        thr = Thread(target=helper)

        with BlockTimer() as t:
            thr.start()
            res = self.bd.get(15, timeout=0.002)
        thr.join()

        self.assertEqual(res, None)
        # Timed out
        self.assertGreaterEqual(t.elapsed, 0.002)

    def test_07_blocking_other_first(self):
        def helper():
            time.sleep(0.001)
            self.bd.put(14, -2)
            time.sleep(0.001)
            self.bd.put(15, 1)

        thr = Thread(target=helper)

        with BlockTimer() as t:
            thr.start()
            res = self.bd.get(15, timeout=0.003)
        thr.join()

        self.assertEqual(res, 1)
        # Blocked until the correct value was added
        self.assertGreaterEqual(t.elapsed, 0.002)
        # Unblocked as soon as the value was added
        self.assertLess(t.elapsed, 0.003)

    def test_08_noblock_after_added(self):
        def helper():
            time.sleep(0.001)
            self.bd.put(-3, 4)

        thr = Thread(target=helper)
        thr.start()
        res = self.bd.get(-3, timeout=0.003)
        with BlockTimer() as t:
            res = self.bd.get(-3, timeout=0.001)
        self.assertLess(t.elapsed, 0.001)

    def test_09_multithread_get(self):
        def helper1():
            res = self.bd.get(105)
            self.assertEqual(res, -15)

        def helper2():
            res = self.bd.get(105)
            self.assertEqual(res, -15)

        thr1 = Thread(target=helper1)
        thr2 = Thread(target=helper2)
        thr1.start()
        thr2.start()
        time.sleep(0.001)
        self.bd.put(105, -15)
        thr1.join()
        thr2.join()


if __name__ == '__main__':
    unittest.main()
