#!/usr/bin/env python3

import sys
import os.path
sys.path.insert(0, os.path.dirname(os.path.abspath(sys.argv[0])))

from epona import EponaAdapter, EponaSwitch
from ipaddress import IPv4Address, IPv4Interface, IPv4Network
from physical import Adapter, BroadcastLink, BROADCAST_MAC, MARE_PROTONUM
import random
from test_phy import MockAdapter
from threading import Thread
import time

import unittest
import unittest.mock as mock

TEST_NET = IPv4Network("10.1.234.0/23")


def MockEponaAdapter(*args, **kwargs):
    a = EponaAdapter(*args, **kwargs)
    a.input = mock.MagicMock(name='self.input', autospec=True)
    return a


class A_Part1(unittest.TestCase):
    """
    Unit tests for the EponaAdapter class (link-layer addressing).

    The MockEponaAdapter class is an EponaAdapter with the .input() method
    mocked out, allowing us to detect which datagrams are accepted by the
    adapter.
    """

    def setUp(self):
        self.ips = (IPv4Interface((addr, TEST_NET.prefixlen)) for addr in TEST_NET.hosts())
        self.rtr = next(self.ips)
        self.link = BroadcastLink(name="part1-link")
        self.a = MockEponaAdapter(b'ePoNa~', next(self.ips), self.rtr)
        self.a.plug(self.link)
        self.b = MockEponaAdapter(b'\xfftest\xfe', next(self.ips), self.rtr)
        self.b.plug(self.link)
        self.c = MockEponaAdapter(b'90\\,t%', next(self.ips), self.rtr)
        self.c.plug(self.link)
        self.d = MockEponaAdapter(b'\x82\x99...\xc9', next(self.ips), self.rtr)
        self.d.plug(self.link)

    def test_01_output_transmits_something(self):
        """
        Each call to output() attempts to transmit some data.
        """
        with mock.patch.object(self.link, 'tx'):
            # Valid destination
            self.a.output(0x9cc0, self.b.hwaddr, b'some data')
            self.link.tx.assert_called_once()

            # Unrecognized destination
            self.link.tx.reset_mock()
            self.b.output(0x0101, b'\xffrest\xfe', b'some more data')
            self.link.tx.assert_called_once()

    def test_02_datagram_successfully_conveyed(self):
        """
        The same datagram and protonum given to output() on the sender are
        passed to input() on the receiver.
        """
        self.a.output(0xbe42, self.b.hwaddr, b'test-datagram conveyed')
        self.b.output(0x9291, self.a.hwaddr, b'test-datagram conveyed TWO')
        self.a.input.assert_called_with(0x9291, b'test-datagram conveyed TWO')
        self.b.input.assert_called_with(0xbe42, b'test-datagram conveyed')

    def test_03_unicast_accepted_only_by_destination(self):
        """
        Unicast frames are accepted only by the adapter with the correct
        destination MAC address, which could be none of them.
        """

        self.b.output(0x1293, self.c.hwaddr, b'from b to c with love')
        self.a.input.assert_not_called()
        self.b.input.assert_not_called()
        self.c.input.assert_called_with(0x1293, b'from b to c with love')
        self.d.input.assert_not_called()

        self.a.input.reset_mock()
        self.b.input.reset_mock()
        self.c.input.reset_mock()
        self.d.input.reset_mock()

        self.b.output(0x1293, b'NOBODy', b'howling a\t the wi\nd')
        self.a.input.assert_not_called()
        self.b.input.assert_not_called()
        self.c.input.assert_not_called()
        self.d.input.assert_not_called()

        self.a.input.reset_mock()
        self.b.input.reset_mock()
        self.c.input.reset_mock()
        self.d.input.reset_mock()

        self.d.output(0xbbb4, self.b.hwaddr, b'from d to b with loathing')
        self.a.input.assert_not_called()
        self.b.input.assert_called_with(0xbbb4, b'from d to b with loathing')
        self.c.input.assert_not_called()
        self.d.input.assert_not_called()

    def test_05_broadcast_accepted_by_all(self):
        """
        Broadcast frames are accepted by any adapter which receives them.
        """
        self.b.output(0xf00f, BROADCAST_MAC, b"hello everybody I'm a baby seal")
        self.a.input.assert_called_once_with(0xf00f, b"hello everybody I'm a baby seal")
        self.b.input.assert_not_called()
        self.c.input.assert_called_once_with(0xf00f, b"hello everybody I'm a baby seal")
        self.d.input.assert_called_once_with(0xf00f, b"hello everybody I'm a baby seal")

    def test_06_lots_of_protos(self):
        """
        Any byte can be used as part of the protonum.
        """
        for protonum in range(0x00ff, 0x8000, 0x00ff):
            self.a.output(protonum, self.b.hwaddr, b'yes, it works')
            self.b.input.assert_called_once_with(protonum, b'yes, it works')
            self.b.input.reset_mock()

    def test_07_lots_of_payloads(self):
        """
        Any byte can be used as part of the payload.
        """
        allbytes = bytes(range(256))
        for shift in range(256):
            payload = allbytes[shift:] + allbytes[:shift]
            self.c.output(shift, self.d.hwaddr, payload)
            self.d.input.assert_called_once_with(shift, payload)
            self.d.input.reset_mock()

    def test_08_lots_of_macs(self):
        """
        Any byte can be used as part of a MAC address.
        """

        # The goal here is to use every byte at least once, both in the source
        # and destination MAC address, to make sure nothing breaks
        macs = [n.to_bytes(6, byteorder='big') for n in
                range(0x56d62a81ff2b, 0x820000000000, 0x00feff00ff01)]
        ads = [MockEponaAdapter(mac, next(self.ips), self.rtr) for mac in macs]
        for ad in ads:
            ad.plug(self.link)

        # Each adapter sends to the address three down in the list
        for src, dst in zip(ads, ads[3:] + ads[:3]):
            srcmac = src.hwaddr.hex()
            dstmac = dst.hwaddr.hex()
            payload = "hi {} this is {}!".format(dstmac, srcmac).encode()
            src.output(0x412a, dst.hwaddr, payload)

        for src, dst in zip(ads, ads[3:] + ads[:3]):
            srcmac = src.hwaddr.hex()
            dstmac = dst.hwaddr.hex()
            payload = "hi {} this is {}!".format(dstmac, srcmac).encode()
            dst.input.assert_called_once_with(0x412a, payload)

    def test_09_corrupted_frames(self):
        """
        Corrupted frames are dropped by all receivers.
        """
        for trial in range(100):
            self.link.corrupt_next()
            self.b.output(0xfc00 | trial, BROADCAST_MAC, b'this is a payload that has a number of bytes in it')
        self.a.input.assert_not_called()
        self.b.input.assert_not_called()
        self.c.input.assert_not_called()
        self.d.input.assert_not_called()

        self.c.output(0xde44, BROADCAST_MAC, b'this is a payload that will be transmitted without errors')

        for trial in range(100):
            self.link.corrupt_next()
            self.d.output(0xfb00 | trial, BROADCAST_MAC, b'this round 2 still has a number of bytes in it')

        self.a.input.assert_called_once_with(0xde44, b'this is a payload that will be transmitted without errors')
        self.b.input.assert_called_once_with(0xde44, b'this is a payload that will be transmitted without errors')
        self.c.input.assert_not_called()
        self.d.input.assert_called_once_with(0xde44, b'this is a payload that will be transmitted without errors')


class B_Part2(unittest.TestCase):
    """
    Unit tests for the EponaSwitch class.

    EponaAdapters are used here to generate valid EPONA frames, and
    MockAdapters are used to detect whether a frame has been forwarded to their
    attached link.
    """

    def setUp(self):
        # Make the addresses different from the previous round
        self.ips = (IPv4Interface((addr, TEST_NET.prefixlen)) for addr in
                    reversed(list(TEST_NET.hosts())))
        self.rtr = next(self.ips)
        self.links = [BroadcastLink(name='part2-link' + str(n)) for n in range(6)]
        self.a = EponaAdapter(bytes.fromhex('76870ecbbf69'), next(self.ips), self.rtr)
        self.b = EponaAdapter(bytes.fromhex('a4296cbdd835'), next(self.ips), self.rtr)
        macbytes = bytes(range(140, 176))
        self.ma = [MockAdapter(macbytes[n * 6:][:6], next(self.ips), self.rtr) for n in range(6)]

        # Setup: one switch with a link connected to each port, and a
        # MockAdapter on each link to detect frames
        self.s1 = EponaSwitch(6)
        for n in range(6):
            self.ma[n].plug(self.links[n])
            self.s1.plug(n, self.links[n])

        # Connect active adapters to ports 2 and 3
        self.a.plug(self.links[2])
        self.b.plug(self.links[3])

    def test_01_no_other_links_unicast(self):
        """
        Switch works if there are unattached ports (unicast).
        """
        for port in range(1, 6):
            self.s1.unplug(port)
        self.a.output(0x99ba, bytes.fromhex('882592985205'), b'unattached!unicast')
        self.ma[0].rx.assert_not_called()
        self.ma[1].rx.assert_not_called()
        self.ma[2].rx.assert_called_once()
        self.ma[3].rx.assert_not_called()
        self.ma[4].rx.assert_not_called()
        self.ma[5].rx.assert_not_called()

    def test_02_no_other_links_broadcast(self):
        """
        Switch works if there are unattached ports (broadcast).
        """
        for port in range(1, 6):
            self.s1.unplug(port)
        self.b.output(0x94ba, BROADCAST_MAC, b'unattached!BROADcast')
        self.ma[0].rx.assert_not_called()
        self.ma[1].rx.assert_not_called()
        self.ma[2].rx.assert_not_called()
        self.ma[3].rx.assert_called_once()
        self.ma[4].rx.assert_not_called()
        self.ma[5].rx.assert_not_called()

    def test_03_flood_unseen_mac(self):
        """
        Switch floods unseen destination address to all ports.
        """
        self.a.output(0x1001, bytes.fromhex('8a1d2cea869a'), b'unseen-dmac')
        for n in range(0, 6):
            # ma[2] is called directly by link 2, others from switch
            self.ma[n].rx.assert_called_once()

    def test_04_flood_unseen_mac_exists(self):
        """
        Switch floods unseen destination address to all ports.
        """
        self.a.output(0x1002, self.ma[3].hwaddr, b'unseen-dmac2')
        for n in range(0, 6):
            # ma[2] is called directly by link 2, others from switch
            self.ma[n].rx.assert_called_once()

    def test_05_broadcast(self):
        """
        Switch floods broadcast frames to all ports.
        """
        self.b.output(0x4001, BROADCAST_MAC, b't3ll the World!')
        for n in range(0, 6):
            # ma[2] is called directly by link 2, others from switch
            self.ma[n].rx.assert_called_once()

    def test_06_switch_learning(self):
        """
        Switch forwards selectively once it has learned an address mapping.
        """
        self.a.output(0x1003, self.ma[0].hwaddr, b'learn-this')
        for n in range(0, 6):
            self.ma[n].rx.reset_mock()

        self.b.output(0x1003, self.a.hwaddr, b'seenit')
        self.ma[0].rx.assert_not_called()
        self.ma[1].rx.assert_not_called()
        self.ma[2].rx.assert_called_once()
        self.ma[3].rx.assert_called_once()
        self.ma[4].rx.assert_not_called()
        self.ma[5].rx.assert_not_called()

    def test_07_no_backwarding(self):
        """
        Switch will not forward a packet back to the port it arrived on.
        """
        # Put active adapters on the same broadcast link
        self.b.plug(self.links[2])

        # Let the switch learn that a is connected to port 2
        self.a.output(0x1004, self.ma[0].hwaddr, b'learn-this')
        for n in range(0, 6):
            self.ma[n].rx.reset_mock()

        # Try sending between nodes on link 2.
        self.b.output(0x1005, self.a.hwaddr, b'h\xaandled loc\ally')

        # Link 0 will see one transmission (from the adapter), and no link
        # should see a transmission from the switch
        self.ma[0].rx.assert_not_called()
        self.ma[1].rx.assert_not_called()
        self.ma[2].rx.assert_called_once()
        self.ma[3].rx.assert_not_called()
        self.ma[4].rx.assert_not_called()
        self.ma[5].rx.assert_not_called()

    def test_09_corrupted_frames(self):
        """
        Switch will not forward corrupted frames.
        """
        for trial in range(100):
            self.links[2].corrupt_next()
            self.a.output(0xbc00 | trial, BROADCAST_MAC, b'this is another payload that has another number of bytes in it')
        self.ma[0].rx.assert_not_called()
        self.ma[1].rx.assert_not_called()
        self.assertEqual(self.ma[2].rx.call_count, 100)
        self.ma[3].rx.assert_not_called()
        self.ma[4].rx.assert_not_called()
        self.ma[5].rx.assert_not_called()

        self.a.output(0x2e44, BROADCAST_MAC, b'this is another payload that will be transmitted without errors')

        for trial in range(100):
            self.links[3].corrupt_next()
            self.b.output(0xbb00 | trial, BROADCAST_MAC, b'this round 2 still has another number of bytes in it')

        self.ma[0].rx.assert_called_once()
        self.ma[1].rx.assert_called_once()
        self.assertEqual(self.ma[2].rx.call_count, 101)
        self.assertEqual(self.ma[3].rx.call_count, 101)
        self.ma[4].rx.assert_called_once()
        self.ma[5].rx.assert_called_once()


class C_Part3(unittest.TestCase):
    """
    Unit tests for the EponaAdapter class (network-layer addressing).
    """

    def setUp(self):
        self.link = BroadcastLink(name="part3-link")
        self.rtr = MockEponaAdapter(
            bytes.fromhex("d4aa17521c20"),
            IPv4Interface("10.23.42.60/21"),
            IPv4Address("0.0.0.0"),
        )
        self.a = MockEponaAdapter(
            bytes.fromhex("1de3adfc46f6"),
            IPv4Interface("10.23.42.192/21"),
            self.rtr.iface.ip,
        )
        self.b = MockEponaAdapter(
            bytes.fromhex("7f36cc432c8d"),
            IPv4Interface("10.23.40.74/21"),
            self.rtr.iface.ip,
        )
        self.c = MockEponaAdapter(
            bytes.fromhex("1e78061448e2"),
            IPv4Interface("10.23.41.100/21"),
            self.rtr.iface.ip,
        )
        self.d = MockEponaAdapter(
            bytes.fromhex("34f9ffe2ab05"),
            IPv4Interface("10.23.41.219/21"),
            self.rtr.iface.ip,
        )

        self.rtr.plug(self.link)
        self.a.plug(self.link)
        self.b.plug(self.link)
        self.c.plug(self.link)
        self.d.plug(self.link)

    def test_01_output_ip(self):
        """
        IP-addressed datagrams are delivered by the correct adapter only.
        """
        self.a.output_ip(0x3250, self.c.iface.ip.packed, b'old macdonald had a farm')
        self.b.output_ip(0x3201, self.a.iface.ip.packed, b'eieio')

        self.rtr.input.assert_not_called()
        self.a.input.assert_called_once_with(0x3201, b'eieio')
        self.b.input.assert_not_called()
        self.c.input.assert_called_once_with(0x3250, b'old macdonald had a farm')
        self.d.input.assert_not_called()

    def test_02_no_such_host(self):
        """
        Adapter.NoRouteToHost is raised when a network-layer address cannot be
        resolved to a link-layer address.
        """
        addr = bytes((10, 23, 41, 11))
        with self.assertRaises(Adapter.NoRouteToHost):
            self.a.output_ip(0x6789, addr, b"nope")

        addr = bytes((10, 23, 47, 88))
        with self.assertRaises(Adapter.NoRouteToHost):
            self.a.output_ip(0x9876, addr, b"nope 2.0")

    def test_03_default_gateway(self):
        """
        Frames are sent to the default gateway when appropriate.
        """
        addr = bytes((10, 23, 49, 224))
        self.a.output_ip(0x1e1b, addr, b"outbound traffic")

        self.rtr.input.assert_called_once_with(0x1e1b, b"outbound traffic")

        self.rtr.input.reset_mock()
        addr = bytes((192, 138, 89, 25))
        self.a.output_ip(0x1e1c, addr, b"outbound train")

        self.rtr.input.assert_called_once_with(0x1e1c, b"outbound train")

    def test_04_mare_corruption(self):
        """
        Address resolution succeeds even if some frames get corrupted.
        """
        self.link.corrupt_next()
        self.a.output_ip(0x3252, self.c.iface.ip.packed, b'in west philadelphia')
        self.link.corrupt_next()
        self.b.output_ip(0x3203, self.a.iface.ip.packed, b'born and raised')

        self.rtr.input.assert_not_called()
        self.a.input.assert_called_once_with(0x3203, b'born and raised')
        self.b.input.assert_not_called()
        self.c.input.assert_called_once_with(0x3252, b'in west philadelphia')
        self.d.input.assert_not_called()


class D_IntegrationTests(unittest.TestCase):
    """
    Placeholder for integration tests for the EPONA project.  None are provided
    at this time.
    """

    def setUp(self):
        pass


if __name__ == '__main__':
    unittest.main()
