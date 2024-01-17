#!/usr/bin/env python3

import threading
from ipaddress import IPv4Address, IPv4Interface, IPv4Network
from physical import Adapter, MultiportNode, BROADCAST_MAC, MARE_PROTONUM


class EponaAdapter(Adapter):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        #key: source IP addr
        #value: source Mac addr
        self.arpTable = dict()
        self.arpMessageRecieved = False
        self.timeout = threading.Event()

    def output(self, protonum, dst, dgram):
        """
        Called when the network layer wishes to transmit a datagram to a
        destination host. Provides the protocol number, destination MAC
        address, and datagram contents as bytes.
        """
        frame = Frame(protonum, dst, self.hwaddr, dgram)
        self.tx(frame.toBytes())

    def rx(self, frame):
        """
        Called when a frame arrives at the adapter.  Provides the frame
        contents as bytes.
        """
        completeFrame = Frame.toFrame(frame)
        if not completeFrame.ConfirmChecksum():
            return
        elif completeFrame.protocol == MARE_PROTONUM:
            self.arpFrameRecievedProcedure(frame)
        elif (self.hwaddr == completeFrame.dstMacAdr or BROADCAST_MAC == completeFrame.dstMacAdr):
            self.input(completeFrame.protocol, completeFrame.datagram)
    
    def arpFrameRecievedProcedure(self, frame):
        completeFrame = ArpFrame.toFrame(Frame.toFrame(frame).datagram)
        if completeFrame.dstIpAdr == self.iface.ip.packed: #The correct IP destination has been found
            self.arpTable[completeFrame.sourceIpAdr] = completeFrame.sourceMacAdr
            if completeFrame.isSuccess == b'0xff' and completeFrame.dstMacAdr == self.hwaddr:
                self.successfulArpMessageRecieved()
                return
            self.output_ip(MARE_PROTONUM, completeFrame.sourceIpAdr, 
                           ArpFrame(completeFrame.sourceMacAdr, self.hwaddr, completeFrame.sourceIpAdr, 
                                    self.iface.ip.packed, True).toBytes()) #Send home
    
    def successfulArpMessageRecieved(self):
        self.arpMessageRecieved = True
        self.timeout.set()

    def output_ip(self, protonum, addr, dgram):
        """
        Called when the network layer wishes to transmit a datagram to a
        destination host.  Provides the protocol number, destination IPv4
        address as four bytes, and datagram contents as bytes.
        """
        if IPv4Address(addr) not in self.iface.network: #Sends to the nearest gateway router
            if self.gateway.packed not in self.arpTable:
                self.arpIpDiscoverProcess(self.gateway.packed)
            self.output_ip(protonum, self.gateway.packed, dgram)
        elif addr in self.arpTable:
            self.output(protonum, self.arpTable[addr], dgram)
        else:
            self.arpIpDiscoverProcess(addr)
            self.output_ip(protonum, addr, dgram)

    def arpIpDiscoverProcess(self, addr):
        arpFrame = ArpFrame(self.hwaddr, self.hwaddr, addr, self.iface.packed)
        arpFrameBytes = arpFrame.toBytes()
        count = 3
        self.timeout.clear()
        while count > 0:
            self.output(MARE_PROTONUM, BROADCAST_MAC, arpFrameBytes)
            self.timeout.wait(0.1)
            if self.arpMessageRecieved:
                self.arpMessageRecieved = False
                return
            count -= 1
        raise self.NoRouteToHost

class EponaSwitch(MultiportNode):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        #key: source port MAC addr
        #value: port
        self.switchingTable = dict()

    def rx(self, port, frame):
        """
        Called when a frame arrives at any port.  Provides the port number as
        an int and the frame contents as bytes.
        """
        completeFrame = Frame.toFrame(frame)
        if not completeFrame.ConfirmChecksum():
            return 
        if completeFrame.dstMacAdr in self.switchingTable:
            if self.switchingTable[completeFrame.dstMacAdr] != port:
                self.forward(self.switchingTable[completeFrame.dstMacAdr], frame)
            return
        self.switchingTable[completeFrame.sourceMacAdr] = port
        self.broadcast(frame, port)

    def broadcast(self, frame, port):
        index = 0
        while index < self.nports:
            if index != port:
                self.forward(index, frame)
            index += 1
        
class Frame():
    """
    Frame Formatting:
        Protocol Number = 6 bytes
        Destination MAC Address = 6 bytes
        Source MAC Address = 6 bytes
        Checksum = 4 bytes
        Datagram
    """

    def __init__(self, protocol, dstMacAdr, sourceMacAdr, datagram) -> None:
        self.protocol = protocol
        self.dstMacAdr = dstMacAdr
        self.sourceMacAdr = sourceMacAdr
        self.datagram = datagram
        self.checksum = self.CreateChecksum()

    def toFrame(byteStream):
        protocol = int.from_bytes(byteStream[0:6], "big")
        dstMacAdr = byteStream[6:12]
        sourceMacAdr = byteStream[12:18]
        checksum = byteStream[18:22]
        datagram = byteStream[22:]
        
        frame = Frame(protocol, dstMacAdr, sourceMacAdr, datagram)
        frame.checksum = checksum
        return frame

    def toBytes(self):
        byteResult = b''
        byteResult += self.protocol.to_bytes(6, "big")
        byteResult += self.dstMacAdr
        byteResult += self.sourceMacAdr
        byteResult += self.checksum
        byteResult += self.datagram
        return byteResult

#region ChecksumHelperMethods

    def CreateChecksum(self):
        self.checksum= b''
        checksum = 0
        checksumData = self.toBytes()
        for byte in checksumData:
            checksum ^= byte
        return checksum.to_bytes(4, "big")
    
    def ConfirmChecksum(self):
        originalChecksum = self.checksum
        checksum = self.CreateChecksum()
        return checksum == originalChecksum

#endregion

class ArpFrame():
    """
    Frame Formatting:
        Destination MAC Address = 6 bytes
        Source MAC Address = 6 bytes
        Destination IP Address = 4 bytes
        Source IP Address = 4 bytes
        Is Successful Flag = 1 byte
    """

    def __init__(self, dstMacAdr, sourceMacAdr, dstIpAdr, sourceIpAdr, isSuccessfulFlag = False) -> None:
        self.dstMacAdr = dstMacAdr
        self.sourceMacAdr = sourceMacAdr
        self.dstIpAdr = dstIpAdr
        self.sourceIpAdr = sourceIpAdr
        self.isSuccess = b'0xff' if isSuccessfulFlag else b''

    def toFrame(byteStream):
        dstMacAdr = byteStream[0:6]
        sourceMacAdr = byteStream[6:12]
        dstIpAdr = byteStream[12:16]
        sourceIpAdr = byteStream[16:20]  
        isSuccess = byteStream[20:] != b''
        return ArpFrame(dstMacAdr, sourceMacAdr, dstIpAdr, sourceIpAdr, isSuccess)

    def toBytes(self):
        byteResult = b''
        byteResult += self.dstMacAdr
        byteResult += self.sourceMacAdr
        byteResult += self.dstIpAdr
        byteResult += self.sourceIpAdr
        byteResult += self.isSuccess
        return byteResult