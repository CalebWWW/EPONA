#!/usr/bin/env python3

from abc import abstractmethod, ABC
from collections.abc import ByteString
import random
import os
import sys
from typing import Optional

BROADCAST_MAC = bytes.fromhex('ff ff ff ff ff ff')
MARE_PROTONUM = 0x0806


def _hexdump(data):
    for ofs in range(0, len(data), 16):
        line = data[ofs:ofs+16]
        hex1 = ' '.join('%02x' % c for c in line[:8])
        hex2 = ' '.join('%02x' % c for c in line[8:])
        disp = ''.join(chr(c) if c in range(32, 128) else '.' for c in line)
        print('%08x  %-23s  %-23s  |%s|' % (ofs, hex1, hex2, disp),
              file=sys.stderr)
    print('%08x' % (len(data),), file=sys.stderr)


class Node(ABC):
    @abstractmethod
    def rx_link(self, link: 'CommunicationsLink', frame: ByteString): ...


class CommunicationsLink(ABC):
    @abstractmethod
    def attach(self, node: Node): ...

    @abstractmethod
    def detach(self, node: Node): ...

    @abstractmethod
    def tx(self, sender: Node, frame: ByteString): ...


class BroadcastLink(CommunicationsLink):
    def __init__(self, name=None, debug=None):
        if name is None:
            name = "link"
        if debug is None:
            debug = 'NET_DEBUG' in os.environ
        self._name = name
        self._debug = debug
        self._nodes: set[Node] = set()
        self._corrupt = False

    def attach(self, node: Node):
        self._nodes.add(node)

    def detach(self, node: Node):
        self._nodes.remove(node)

    def corrupt_next(self):
        self._corrupt = True

    def tx(self, sender: Node, frame: ByteString):
        assert sender in self._nodes, "BroadcastLink received frame from unattached node"

        if not isinstance(frame, ByteString):
            raise TypeError("Link can only transmit bytes")

        frame = bytes(frame)
        if self._corrupt:
            # Choose a random byte
            pos = random.randint(0, len(frame) - 1)
            before, byte, after = frame[:pos], frame[pos], frame[pos + 1:]
            # Introduce a random single-bit error
            byte ^= 1 << random.randint(0, 7)
            frame = before + bytes((byte,)) + after
        if self._debug:
            print('Frame on link "%s"%s:' % (self._name, ' (CORRUPTED)' if self._corrupt else ''),
                  file=sys.stderr)
            _hexdump(frame)
        for node in self._nodes:
            if node != sender:
                node.rx_link(self, frame)
        self._corrupt = False


class Adapter(Node):
    """Protocol-agnostic base class for network adapters/interfaces"""

    class NoRouteToHost(Exception):
        """
        Exception raised when attempting to contact a network-layer address
        which cannot be resolved to an appropriate next hop.
        """

    def __init__(self, hwaddr, iface, gateway, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._link = None
        self._hwaddr = hwaddr
        self._iface = iface
        self._gateway = gateway

    # We use @property to make these values effectively read-only (by not
    # providing corresponding setter methods)
    @property
    def hwaddr(self):
        return self._hwaddr

    @property
    def iface(self):
        return self._iface

    @property
    def gateway(self):
        return self._gateway

    def plug(self, link: CommunicationsLink):
        if self._link is not None:
            self.unplug()
        self._link = link
        self._link.attach(self)

    def unplug(self):
        if self._link is None:
            return
        self._link.detach(self)
        self._link = None

    def rx_link(self, link: CommunicationsLink, frame: ByteString):
        assert link is self._link, "Adapter received frame from unattached link"

        self.rx(frame)

    def tx(self, frame):
        if self._link is None:
            return
        self._link.tx(self, frame)

    # This will be mocked out for tests
    def input(self, protonum, dgram): ...

    @abstractmethod
    def output(self, protonum, dst, dgram): ...

    @abstractmethod
    def rx(self, frame: ByteString): ...

    @abstractmethod
    def output_ip(self, protonum, addr, dgram): ...


class MultiportNode(Node):
    def __init__(self, num_ports):
        self._nports = num_ports
        self._ports: list[Optional[CommunicationsLink]] = [None] * num_ports

    # We use @property to make this value effectively read-only (by not
    # providing a corresponding setter method)
    @property
    def nports(self):
        return self._nports

    def plug(self, portnum: int, link: CommunicationsLink):
        if portnum not in range(len(self._ports)):
            raise IndexError("Invalid port number")

        self.unplug(portnum)
        self._ports[portnum] = link
        link.attach(self)

    def unplug(self, portnum: int):
        if portnum not in range(len(self._ports)):
            raise IndexError("Invalid port number")

        link = self._ports[portnum]
        if link is None:
            return
        self._ports[portnum] = None
        link.detach(self)

    def rx_link(self, link: CommunicationsLink, frame: ByteString):
        assert link in self._ports, "MultiportNode received frame from unattached link"

        inport = self._ports.index(link)
        self.rx(inport, frame)

    def forward(self, outport: int, frame: ByteString):
        if outport not in range(len(self._ports)):
            raise IndexError("Invalid port number")

        link = self._ports[outport]
        if link is None:
            return
        link.tx(self, frame)

    @abstractmethod
    def rx(self, portnum: int, frame: ByteString): ...
