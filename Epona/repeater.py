#!/usr/bin/env python3

from physical import MultiportNode


class Repeater(MultiportNode):
    def rx(self, inport, frame):
        for outport in range(self.nports):
            if outport != inport:
                self.forward(outport, frame)
