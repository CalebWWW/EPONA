#!/usr/bin/env python3

import sys
import os.path
sys.path.insert(0, os.path.dirname(os.path.abspath(sys.argv[0])))

from physical import Adapter, BroadcastLink, CommunicationsLink, MultiportNode, Node

from ipaddress import IPv4Interface, IPv4Address
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


class A0_BroadcastLinkTest(unittest.TestCase):
    def setUp(self):
        self.link = BroadcastLink()
        self.mn = mock.MagicMock(name='node 1', spec=Node)
        self.mn2 = mock.MagicMock(name='node 2', spec=Node)
        self.link.attach(self.mn)
        self.link.attach(self.mn2)

    def test_00_noop(self):
        self.mn.rx_link.assert_not_called()
        self.mn2.rx_link.assert_not_called()

    def test_01_txnonbytes(self):
        with self.assertRaises(TypeError):
            self.link.tx(self.mn, 'test-string')
        with self.assertRaises(TypeError):
            self.link.tx(self.mn, 6)
        with self.assertRaises(TypeError):
            self.link.tx(self.mn, [b'nope'])
        with self.assertRaises(TypeError):
            self.link.tx(self.mn, (3, b'nope'))
        with self.assertRaises(TypeError):
            self.link.tx(self.mn, {8: b'nope'})

    def test_02_onetx(self):
        self.link.tx(self.mn, b'test-onetx')
        self.mn.rx_link.assert_not_called()
        self.mn2.rx_link.assert_called_once_with(self.link, b'test-onetx')

    def test_03_onetx_bytearray(self):
        self.link.tx(self.mn, bytearray(b'test-onetx-bytearray'))
        self.mn.rx_link.assert_not_called()
        self.mn2.rx_link.assert_called_once_with(self.link, b'test-onetx-bytearray')

    def test_04_twotx(self):
        self.link.tx(self.mn, b'test-twotx1')
        self.link.tx(self.mn2, b'test-twotx2')
        self.mn.rx_link.assert_called_once_with(self.link, b'test-twotx2')
        self.mn2.rx_link.assert_called_once_with(self.link, b'test-twotx1')

    def test_05_multitx(self):
        for n in range(10):
            msg = b'test-multitx' + str(n).encode()
            msg2 = msg + msg
            self.link.tx(self.mn, msg)
            self.link.tx(self.mn2, msg2)
            self.mn.rx_link.assert_called_once_with(self.link, msg2)
            self.mn2.rx_link.assert_called_once_with(self.link, msg)
            self.mn.reset_mock()
            self.mn2.reset_mock()

    def test_06_threenodes(self):
        mn3 = mock.MagicMock(name='node 3', spec=Node)
        self.link.attach(mn3)
        self.link.tx(self.mn2, b'test-threenodes')

        self.mn.rx_link.assert_called_once_with(self.link, b'test-threenodes')
        self.mn2.rx_link.assert_not_called()
        mn3.rx_link.assert_called_once_with(self.link, b'test-threenodes')

    def test_07_missedmsg(self):
        mn3 = mock.MagicMock(name='node 3', spec=Node)
        self.link.tx(self.mn2, b'test-missed')
        self.link.attach(mn3)
        mn3.rx_link.assert_not_called()
        self.mn.rx_link.assert_called_once_with(self.link, b'test-missed')
        self.mn2.rx_link.assert_not_called()

    def test_08_detach(self):
        self.link.detach(self.mn2)
        self.link.tx(self.mn, b'test-detach')
        self.mn2.rx_link.assert_not_called()

    def test_09_reattach(self):
        self.link.detach(self.mn2)
        self.link.tx(self.mn, b'test-reattach1')
        self.link.attach(self.mn2)
        self.link.tx(self.mn, b'test-reattach2')
        self.mn2.rx_link.assert_called_once_with(self.link, b'test-reattach2')

    def test_10_only_attached(self):
        self.link.detach(self.mn2)
        with self.assertRaises(AssertionError):
            self.link.tx(self.mn2, b'test-only-attached')


class A1_AdapterTest(unittest.TestCase):
    def setUp(self):
        self.mac = bytes.fromhex('f5e5f8bd99bc')
        self.iface = IPv4Interface("192.168.99.81/24")
        self.gw = IPv4Address("192.168.99.2")
        self.a = MockAdapter(self.mac, self.iface, self.gw)
        self.link = mock.MagicMock(name='link', spec=CommunicationsLink)

    def test_00_noop(self):
        self.link.attach.assert_not_called()
        self.link.detach.assert_not_called()
        self.link.tx.assert_not_called()

    def test_01_plug_link(self):
        self.a.plug(self.link)
        self.link.attach.assert_called_once_with(self.a)
        self.link.detach.assert_not_called()
        self.link.tx.assert_not_called()

    def test_02_plug_unplug(self):
        self.a.plug(self.link)
        self.link.reset_mock()

        self.a.unplug()
        self.link.attach.assert_not_called()
        self.link.detach.assert_called_once_with(self.a)
        self.link.tx.assert_not_called()

    def test_03_unplug_not_plugged(self):
        self.a.unplug()
        self.link.attach.assert_not_called()
        self.link.detach.assert_not_called()
        self.link.tx.assert_not_called()


class A2_MultiportTest(unittest.TestCase):
    def setUp(self):
        self.n = MockMultiport(6)
        self.link = mock.MagicMock(name='link', spec=CommunicationsLink)
        self.link2 = mock.MagicMock(name='link2', spec=CommunicationsLink)

    def test_00_noop(self):
        self.n.rx.assert_not_called()
        self.link.attach.assert_not_called()
        self.link.detach.assert_not_called()
        self.link.tx.assert_not_called()

    def test_01_plug_attaches(self):
        self.n.plug(3, self.link)
        self.n.rx.assert_not_called()
        self.link.attach.assert_called_once_with(self.n)
        self.link.detach.assert_not_called()
        self.link.tx.assert_not_called()

    def test_02_unplug_detaches(self):
        self.n.plug(3, self.link)
        self.link.reset_mock()

        self.n.unplug(3)

        self.n.rx.assert_not_called()
        self.link.attach.assert_not_called()
        self.link.detach.assert_called_once_with(self.n)
        self.link.tx.assert_not_called()

    def test_03_unplug_other_port(self):
        self.n.plug(3, self.link)
        self.link.reset_mock()

        self.n.unplug(2)

        self.n.rx.assert_not_called()
        self.link.attach.assert_not_called()
        self.link.detach.assert_not_called()
        self.link.tx.assert_not_called()

    def test_04_spurious_unplug(self):
        self.n.unplug(0)

        self.n.rx.assert_not_called()
        self.link.attach.assert_not_called()
        self.link.detach.assert_not_called()
        self.link.tx.assert_not_called()

    def test_05_plug_oob(self):
        with self.assertRaises(IndexError):
            self.n.plug(6, self.link)

    def test_06_plug_oob(self):
        with self.assertRaises(IndexError):
            self.n.plug(-1, self.link)

    def test_07_unplug_oob(self):
        with self.assertRaises(IndexError):
            self.n.unplug(6)

    def test_08_unplug_oob(self):
        with self.assertRaises(IndexError):
            self.n.unplug(-1)

    def test_09_double_unplug(self):
        self.n.plug(5, self.link)
        self.link.reset_mock()

        self.n.unplug(5)
        self.n.unplug(5)

        self.n.rx.assert_not_called()
        self.link.attach.assert_not_called()
        self.link.detach.assert_called_once_with(self.n)
        self.link.tx.assert_not_called()

    def test_10_two_links(self):
        self.n.plug(1, self.link)
        self.n.plug(4, self.link2)

        self.link.attach.assert_called_once_with(self.n)
        self.link2.attach.assert_called_once_with(self.n)

        self.link.reset_mock()
        self.link2.reset_mock()

        self.n.unplug(1)
        self.link.detach.assert_called_once_with(self.n)
        self.link2.detach.assert_not_called()

    def test_11_tx(self):
        self.n.plug(2, self.link)
        self.n.forward(2, b'test-11-tx')

        self.link.tx.assert_called_once_with(self.n, b'test-11-tx')

    def test_12_spurious_tx(self):
        self.n.forward(2, b'test-12-spurious')

        self.link.tx.assert_not_called()

    def test_13_tx_after_unplug(self):
        self.n.plug(1, self.link)
        self.link.reset_mock()

        self.n.unplug(1)
        self.n.forward(1, b'test-12-unplug')

        self.link.tx.assert_not_called()

    def test_14_tx_two_links(self):
        self.n.plug(5, self.link)
        self.n.plug(0, self.link2)
        self.link.reset_mock()
        self.link2.reset_mock()

        self.n.forward(0, b'test14-AAA')
        self.n.forward(4, b'test14-BBB')
        self.n.forward(5, b'test14-CCC')

        self.link.tx.assert_called_once_with(self.n, b'test14-CCC')
        self.link2.tx.assert_called_once_with(self.n, b'test14-AAA')

    def test_15_rx_one(self):
        self.n.plug(4, self.link)
        self.n.rx_link(self.link, b'test15-rx1')

        self.n.rx.assert_called_once_with(4, b'test15-rx1')

    def test_16_rx_two(self):
        self.n.plug(2, self.link)
        self.n.plug(3, self.link2)

        self.n.rx_link(self.link2, b'test16-rx1')
        self.n.rx.assert_called_once_with(3, b'test16-rx1')
        self.n.rx.reset_mock()

        self.n.rx_link(self.link, b'test16-rx2')
        self.n.rx.assert_called_once_with(2, b'test16-rx2')

    def test_17_rx_unattached(self):
        self.n.plug(0, self.link2)
        with self.assertRaises(AssertionError):
            self.n.rx_link(self.link, b'test17-unattached')

    def test_18_rx_unplugged(self):
        self.n.plug(2, self.link)
        self.n.unplug(2)
        with self.assertRaises(AssertionError):
            self.n.rx_link(self.link, b'test17-unattached')

    def test_19_plug_detach_attach(self):
        self.n.plug(3, self.link)
        self.link.attach.assert_called_once_with(self.n)
        self.link.reset_mock()

        self.n.plug(3, self.link2)
        self.link.detach.assert_called_once_with(self.n)
        self.link2.attach.assert_called_once_with(self.n)

    def test_20_plug_replaces(self):
        self.n.plug(3, self.link)
        self.n.plug(3, self.link2)
        with self.assertRaises(AssertionError):
            self.n.rx_link(self.link, b'test-20-plug')


if __name__ == '__main__':
    unittest.main()
