---
title: Project 3
geometry:
  - margin=1in
header-includes: |
    \usepackage{djp-pandoc}
    \subtitle{Link layer and address resolution}
    \input{coursedefs}
...

# Overview

Your task in this project is to design and implement a link-layer protocol for Exchanging Packets with Other Nearby Adapters.  The EPONA protocol^[Ok, I actually called it EPONA because it helps the Link carry data from one adapter to its *neigh*-bors.] will be a switched link-layer protocol of your own design which provides for transmission of a frame over a broadcast link to its next-hop destination.  The included network simulator is designed to eliminate concerns about framing and multiple access, so your protocol will not need to account for either of these properties.^[Ethernet and other link-layer protocols are often viewed as consisting of multiple sub-layers.  For added realism, therefore, you may instead claim that these services are "handled by a lower sub-layer."]


# Procedure/requirements

Clone the starter code from the following URL:

    https://github.com/devinpohly/csci357-epona

This codebase contains a low-level network simulator in `physical.py`, a helpful data structure in `blockingdict.py`, a very simple sample in `repeater.py`, and several testsuites.  Your work will be done by filling in the methods of the two classes found in the file `epona.py`, and you may of course add (but not override) any other fields or methods that you need in this file.


## Part 1: Link layer protocol

Implement the first two methods of the `EponaAdapter` class, which provide the logic needed by a network interface to transmit and receive EPONA frames.  Adapters should detect and discard corrupted frames, and the protocol will need to include whatever is necessary to enable this.

An EPONA interface will be identified with a 48-bit MAC address similar to those used in Ethernet.  Throughout the code, these hardware addresses are represented as a `bytes` type of length 6.  For example, the broadcast address `BROADCAST_MAC` is represented as the `bytes` value consisting of six `0xff` bytes.

Each call to the `output` method also includes a 16-bit `protonum` integer.  Much like the EtherType field in Ethernet, this number identifies which protocol is encapsulated in the frame's payload.  For now, you only need to ensure that the receiving adapter will provide the same protocol number when calling `input`.  In Part 3, this value will have a more specific use in your implementation.

The `EponaAdapter` class contains two methods for you to implement in this part:

  * `output(self, protonum, dst, dgram)`: This method is called by the network layer to transmit a datagram to a neighboring node.  The network-layer protocol number and destination MAC address are provided in `protonum` and `dst` respectively, and the bytes of the datagram itself are provided in `dgram`.

  * `rx(self, frame)`: This method is called by the physical layer whenever a frame is received by the interface.  The adapter should ignore this frame if it is corrupted or if, based on the destination address, it should not be processed by this node.  Otherwise, the `self.input` method should be used to deliver the encapsulated datagram to the network layer.

A successful implementation of this part should pass all of the "A_Part1" tests in `test_epona.py`.


## Part 2: Layer-2 switch

Implement the `EponaSwitch` class.  An EPONA switch is a layer-2 device which attempts to selectively forward frames only to the correct port.  To accomplish this, it performs passive self-learning just as an Ethernet switch does: by observing addresses whenever it forwards traffic.  Incoming frames with an unrecognized destination and broadcast frames should be flooded to all other ports.  In no case should the switch ever forward a frame back out the port it arrived from.^[I hereby christen this type of forwarding "backwarding."]  If normal switching logic would cause this to happen, ignore the frame.

As with adapters, EPONA switches should detect and discard corrupted frames without forwarding them.

You may assume that there are no switching loops, so you will not need to worry about implementing a spanning-tree protocol to resolve them.

There is only one method to implement in `EponaSwitch`:

  * `rx(self, port, frame)`: This method is called by the physical layer whenever a frame is received on one of the ports of the switch.  The port number is provided in `port` and the frame bytes in `frame`.  Your implementation here will need to call `self.forward` based on correct switching logic.

A successful implementation of this part should pass all of the "B_Part2" tests in `test_epona.py`.


## Part 3: Address resolution

Add a protocol to `EponaAdapter` for resolving IP addresses to hardware addresses.  This will allow you to implement the final method:

  * `output_ip(self, protonum, addr, dgram)`: This method is called by the network layer when it needs to transmit a datagram.  The IP address of the network-layer destination host is provided as a four-byte `bytes` value, and the result of this method should be to determine the correct link-layer destination for this hop and *call `self.output`* to transmit the datagram.

In order to accomplish this, you will need to design an ARP-like protocol for MAC Address Resolution in EPONA.  The MARE protocol should follow the example of ARP in implementing a simple request/reply protocol, and caching the MAC-to-IP address mappings at each node that receives a MARE reply.  Your implementation should accept unsolicited replies.  Though obviously not ideal for security, this is how ARP often works, and it will simplify your implementation.

The protocol number 0x0806 (`MARE_PROTONUM`) has been reserved for you to use when sending or distinguishing MARE traffic.  MARE frames do not contain datagrams to be delivered to the network layer, so they will be handled entirely by your link-layer code.

Your MARE implementation should retry if no reply is received.  For the purpose of this assignment, use a timeout of 0.1 seconds before retrying, and if resolution times out three times, raise `self.NoRouteToHost`.^[If you are curious about real-world values, the default ARP configuration on Linux waits one second to resend an ARP request, considering the address unreachable after three attempts.]

Completing this part will require you to update the methods from Part 1 in addition to implementing `output_ip`.  A successful implementation of this part should pass the entire `test_epona.py` testsuite.


# Provided classes and API

This section describes the API that you should rely on for your implementation.  You may of course add (but not override) fields and methods in the `EponaAdapter` and `EponaSwitch` classes.


## `EponaAdapter`

The `EponaAdapter` class represents a network interface, such as a NIC on a host or a single input/output port of a router.  As a subclass of `Adapter`, it comes initialized with several fields for you to read:

  - `self.hwaddr`: the hardware (MAC) address of the adapter itself
  - `self.iface`: an `IPv4Interface` object representing the interface's configured IP address and netmask
  - `self.gateway`: the `IPv4Address` of the default gateway router
  - `self.NoRouteToHost`: a reference to an exception class to raise when address resolution fails

The superclass also provides two methods for you to call:

  * `self.input(protonum, dgram)`: Delivers an arriving datagram to the network layer for further processing.  The `protonum` should be whatever value was provided at the sender.

  * `self.tx(frame)`: Transmits the given frame bytes on the attached link.  The frame will then propagate to and be received by all of the other nodes which are attached to that link.


## `EponaSwitch`

The `EponaSwitch` class represents a layer-2 switch for EPONA networks.  As a subclass of `MultiportNode`, it comes initialized with the following field for you to read:

  - `self.nports`: the number of ports on the switch

The superclass also provides a method for you to call:

  - `self.forward(outport, frame)`: forwards the provided frame to port `outport` (between `0` and `self.nports - 1`) if it has a link attached.


## Other classes in `physical.py`

As with RDT, you may examine these if you are curious about how the simulation is implemented, but you should not use any of the fields or methods other than those listed above.


## `Repeater`

The `Repeater` class was originally designed to allow for testing multiple nodes with point-to-point links, and it was no longer needed once `BroadcastLink` was implemented.  I have left it in the codebase as a minimal sample of a `MultiportNode` subclass, but you will not need to use it for anything.


# Tips

  - "Network byte order" is big-endian.  Any addresses supplied as `bytes` are already in network byte order and need not be byte-swapped.

  - As with the RDT project, setting the `NET_DEBUG` environment variable will enable verbose debugging output which includes the exact contents of every frame sent on a communications link.  Since your protocol defines the format of addresses in packets, the debug code cannot show sender/receiver information, but it will include the name of the link (you can find these in the tests).  This will make it clear which link the data was transmitted on, which can be helpful for Part 2.

  - If you didn't do this for RDT, be sure to run `./test_epona.py -h` and peruse the help output to see what options are available.

  - Python's `bytes` objects are suitable for use as keys in a dictionary.

  - There is a reason that each interface is configured not only with its IP address but also with the IP address of its default gateway router.^["Each of you should look not only to your own address, but also to the addresses of routers." - Philippians 2:4, Network Application Study Bible]

  - Python's `ipaddress` module provides some potentially useful functionality, such as constructing an `IPv4Address` object from a `bytes` value.  Its documentation, however, is not very clear in distinguishing the classes it provides:

      - `IPv4Address` represents an IPv4 address by itself, with no additional context.
      - `IPv4Network` represents a specific subnet of IPv4 addresses with a given prefix length (or, equivalently, netmask), but not a specific address within that subnet.
      - An `IPv4Interface` combines the two, representing a specific IPv4 address within a specific subnet.

    Hopefully a brief demonstration will elucidate:

    ```interactive
    >>> |>i = IPv4Interface("10.1.234.5/18")
    >>> |>i2 = IPv4Interface("10.1.234.5/16")
    >>> |>addr = IPv4Address("10.1.234.5")
    >>> |>i.ip == i2.ip == addr
    True
    >>> |>i == i2
    False
    >>> |>i.network
    IPv4Network('10.1.192.0/18')
    >>> |>i2.network
    IPv4Network('10.1.0.0/16')
    ```

    These three classes are also suitable for use as keys in a Python dictionary.

  - ARP has use cases which are not part of the MARE requirements, so there will be fields in the ARP frame structure which it's not necessary to implement analogues for.
