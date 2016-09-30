# -*- coding: utf-8 -*-

""" This file is part of B{Domogik} project (U{http://www.domogik.org}).

License
=======

B{Domogik} is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

B{Domogik} is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with Domogik. If not, see U{http://www.gnu.org/licenses}.

Plugin purpose
==============

Handle bugOne sniffer and the bugOne network

Implements
==========

- BugOne
- BugOneException

@author: Freki <freki@frekilabs.fr>
@copyright: (C) 2007-2016 Domogik project
@license: GPL(v3)
@organization: Domogik
"""

import binascii
import traceback
import threading
import time
from Queue import Queue, Empty, Full
import serial as serial
from domogik.xpl.common.xplconnector import XplTimer
import domogik.tests.common.testserial as testserial
import glob, os, string

PACKET_HELLO  = 0x01
PACKET_PING   = 0x02
PACKET_PONG   = 0x03
PACKET_GET    = 0x04
PACKET_SET    = 0x05
PACKET_VALUES = 0x06


class BugOneException(Exception):
    """
    bugOne exception
    """

    def __init__(self, value):
        Exception.__init__(self)
        self.value = value

    def __str__(self):
        return repr(self.value)

class BugOne():

    def __init__(self, bugone_port, autoreconnect, log, cb_send_xpl, stop, registered_devices, cb_register_thread, fake_device = None):
        self.log = log
        self.stop = stop

        # fake or real device
        self.fake_device = fake_device
        self.bugone_port = bugone_port
        self.autoreconnect = autoreconnect

        self.cb_send_xpl = cb_send_xpl
        self.cb_register_thread = cb_register_thread

        # serial device
        self.registered_devices = registered_devices
        self.bugone = serial.Serial(self.bugone_port, baudrate = 38400, timeout = 1)


    def listen(self, stop):
        """ Start listening to bugOne
        @param stop : an Event to wait for stop request
        """
        self.log.info(u"**** Start listening to bugOne network****")
        # infinite
        try:
            while not stop.isSet():
                self.read()
            return
        except serial.SerialException:
            error = "Error while reading rfxcom device (disconnected ?) : %s" % traceback.format_exc()
            self.log.error(u"{0}".format(error))
            if self.autoreconnect:
                """ Linux might have renamed the port. 
                We make the hypothesis that only one serial device with the
                corresponding pattern exist in the system. This will change when
                the bugone project for sniffer will include a status exchange
                """
                #TODO: add a timer
                while not stop.isSet():
                    self.log.warning("Attempting to reconnect...")
                    portlist = glob.glob(string.rstrip(self.bugone_port,"0123456789") + "*")
                    if not (portlist == []):
                        self.bugone_port = portlist[0]
                        self.log.info("Found new port with correct pattern: " + self.bugone_port)
                        time.sleep(1)
                        self.log.info("Reconnecting to sniffer...")
                        self.bugone = serial.Serial(self.bugone_port, baudrate = 38400, timeout = 1)
                        self.log.info("Reconnection done! :)")
                        #This is ugly (useless recurrence)
                        self.listen(stop)

                        


                
                

                # TODO : raise for using self.force_leave() in bin ?
                return

    def read(self):
        """ Read bugOne device once
            Inspired from the Sniffer Python code
        """
        buf = self.bugone.read(1)
        if (len(buf) != 1):
            return None
        size = ord(buf)
        self.log.info(u"**** Packet size: %s ****" % size)
        data = self.bugone.read(size)
        if (len(data) != size):
            return None
        checksum = ord(self.bugone.read())
        c = 0
        for i in data:
            c ^= ord(i)
        if checksum != c:
            return None
        else:
            self._process_received_data(data)

    def _process_received_data(self, message):
        messageType = self.getPacketType(message)
        srcNodeId = self.getPacketSrc(message)
        destNodeId = self.getPacketDest(message)
        counter = self.getPacketCounter(message)
        self.log.info (u"Message [%s] from %s to %s" % (counter, hex(srcNodeId), hex(destNodeId)))
        if messageType == PACKET_HELLO:
            self.log.info("Hello")
        elif messageType == PACKET_PING:
            self.log.info("Ping")
        elif messageType == PACKET_PONG:
            self.log.info("Pong")
        elif messageType == PACKET_VALUES:
            values = self.readValues(self.getPacketData(message))
            for (srcDevice, destDevice, value) in values:
                self.log.info("- (%s.%s) -> (%s.%s) = %s" % \
                    (srcNodeId, srcDevice, destNodeId, destDevice, value))
                if (srcNodeId,srcDevice) in self.registered_devices:
                    dev = self.registered_devices[(srcNodeId,srcDevice)]
                    self.report_status(dev,value)
        else:
            self.log.info([hex(ord(i)) for i in self.getPacketData(message)])

    def report_status(self, device, value):
        self.cb_send_xpl(schema = "sensor.basic", 
                data = {"device" : device["name"],
                    "type" : device["sensortype"],
                    "current" : float(value)/10})


    def getPacketSrc(self, message):
        return ord(message[0])

    def getPacketDest(self, message):
        return ord(message[1])

    def getPacketRouter(self, message):
        return ord(message[2])

    def getPacketType(self, message):
        return ord(message[3])

    def getPacketCounter(self, message):
        return self.readInteger(message[4:6])

    def getPacketData(self, message):
        return message[6:]

    ### Parse data ###

    def readValues(self, data):
        values = []
        while len(data) > 3:
            srcDevice = ord(data[0])
            destDevice = ord(data[1])
            valueType = data[2]
            value = None
            if valueType == 'I':
                value = self.readInteger(data[3:5])
                data = data[5:]
            elif valueType == 'S':
                count = ord(data[3])
                value = data[4:4+count]
                data = data[4+count:]
            else:
                break
            values.append((srcDevice, destDevice, value))
        return values

    def writeValues(self, values):
        data = ""
        for (srcDeviceId, destDeviceId, value) in values:
            data += chr(srcDeviceId)
            data += chr(destDeviceId)
            if type(value) is int:
                data += 'I' + self.writeInteger(value)
            elif type(value) is str:
                data += 'S' + chr(len(value)) + value
        return data

    def writeDevices(self, devices):
        data = ""
        for (srcDeviceId, destDeviceId) in devices:
            data += chr(srcDeviceId)
            data += chr(destDeviceId)
        return data

    ### Send packet ###

    #def hello(self, sniffer):
    #    sniffer.send(buildPacket(0xFF, PACKET_HELLO))

    #def ping(self, destNodeId, sniffer):
    #    sniffer.send(buildPacket(destNodeId, PACKET_PING))

    #def pong(self, destNodeId, sniffer):
    #    sniffer.send(buildPacket(destNodeId, PACKET_PONG))

    #def setValue(self, destNodeId, srcDeviceId, destDeviceId, value, sniffer):
    #    data = writeValues([(srcDeviceId, destDeviceId, value),(0xFF,0xFF,0)])
    #    sniffer.send(buildPacket(destNodeId, PACKET_SET, data=data))

    #def getValue(self, destNodeId, srcDeviceId, destDeviceId, sniffer):
    #    data = writeDevices([(srcDeviceId, destDeviceId),(0xFF,0xFF)])
    #    sniffer.send(buildPacket(destNodeId, PACKET_GET, data=data))
    #    message = sniffer.waitForMessage()
    #    if message and getPacketType(message) == PACKET_VALUES:
    #        values = readValues(getPacketData(message))
    #        return values[0][2]
    #    return None

    #### TOOLS ###

    ## return packet formatted according bugOne protocol (do not send)
    ## packetType can be: 1 Hello, 2 Ping, 3 Pong, 4 Get, 5 Set, 6 Values
    #def buildPacket(self, destNodeId, packetType, srcNodeId = 0, lastCounter = 0, data = None):
    #    message  = chr(srcNodeId)   # Src
    #    message += chr(destNodeId)  # Dest
    #    message += chr(0)           # Router
    #    message += chr(packetType)  # Type
    #    message += writeInteger(lastCounter) # Counter
    #    if data:
    #        message += data
    #    return message

    def readInteger(self, bytes, bigEndian = True):
        res = 0
        if bigEndian: bytes = bytes[::-1]
        for b in bytes:
            res = res << 8
            res += ord(b)
        return res

    def writeInteger(self, value):
        return chr(value & 0x00FF) + chr((value & 0xFF00) >> 8)

