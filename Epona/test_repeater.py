#!/usr/bin/env python3

import sys
import os.path
sys.path.insert(0, os.path.dirname(os.path.abspath(sys.argv[0])))

from physical import Adapter, BroadcastLink, CommunicationsLink, MultiportNode, Node
from repeater import Repeater

import unittest
import unittest.mock as mock


def mocked_abstract(cls):
    def ctor(*args, **kwargs):
        methods = cls.__abstractmethods__
        with mock.patch.object(cls, '__abstractmethods__', frozenset()):
            a = cls(*args, **kwargs)
            for m in methods:
                setattr(a, m, mock.MagicMock(spec=getattr(a, m)))
        return a
    return ctor


MockAdapter = mocked_abstract(Adapter)
MockMultiport = mocked_abstract(MultiportNode)


class A0_RepeaterUnitTest(unittest.TestCase):
    def setUp(self):
        self.hub = Repeater(6)
        self.link = mock.MagicMock(name='link', spec=CommunicationsLink)
        self.link2 = mock.MagicMock(name='link2', spec=CommunicationsLink)
        self.link3 = mock.MagicMock(name='link3', spec=CommunicationsLink)

    def test_01_no_echo(self):
        self.hub.plug(2, self.link)
        self.hub.rx_link(self.link, b'test-01-no-echo')

        self.link.tx.assert_not_called()

    def test_02_two_links(self):
        self.hub.plug(3, self.link)
        self.hub.plug(1, self.link2)
        self.hub.rx_link(self.link, b'test-02-two-AAA')

        self.link.tx.assert_not_called()
        self.link2.tx.assert_called_once_with(self.hub, b'test-02-two-AAA')
        self.link.reset_mock()
        self.link2.reset_mock()

        self.hub.rx_link(self.link2, b'test-02-two-BBB')
        self.link2.tx.assert_not_called()
        self.link.tx.assert_called_once_with(self.hub, b'test-02-two-BBB')

    def test_03_three_links(self):
        self.hub.plug(0, self.link)
        self.hub.plug(5, self.link2)
        self.hub.plug(4, self.link3)
        self.hub.rx_link(self.link, b'test-03-three-AAA')

        self.link.tx.assert_not_called()
        self.link2.tx.assert_called_once_with(self.hub, b'test-03-three-AAA')
        self.link3.tx.assert_called_once_with(self.hub, b'test-03-three-AAA')
        self.link.reset_mock()
        self.link2.reset_mock()
        self.link3.reset_mock()

        self.hub.rx_link(self.link2, b'test-03-three-BBB')
        self.link.tx.assert_called_once_with(self.hub, b'test-03-three-BBB')
        self.link2.tx.assert_not_called()
        self.link3.tx.assert_called_once_with(self.hub, b'test-03-three-BBB')
        self.link.reset_mock()
        self.link2.reset_mock()
        self.link3.reset_mock()

        self.hub.rx_link(self.link3, b'test-03-three-CCC')
        self.link.tx.assert_called_once_with(self.hub, b'test-03-three-CCC')
        self.link2.tx.assert_called_once_with(self.hub, b'test-03-three-CCC')
        self.link3.tx.assert_not_called()


if __name__ == '__main__':
    unittest.main()
