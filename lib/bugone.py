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
from collections import deque
from Queue import Queue, Empty, Full
import serial as serial
from domogik.xpl.common.xplconnector import XplTimer
import domogik.tests.common.testserial as testserial
import domogik_packages.plugin_bugone.lib.bugoneprotocol as bugoneprotocol
import glob, os, string

PACKET_HELLO  = 0x01
PACKET_PING   = 0x02
PACKET_PONG   = 0x03
PACKET_GET    = 0x04
PACKET_SET    = 0x05
PACKET_VALUES = 0x06
PACKET_SLEEP  = 0x07


class BugOneException(Exception):
    """
    bugOne exception
    """

    def __init__(self, value):
        Exception.__init__(self)
        self.value = value

    def __str__(self):
        return repr(self.value)

class BugOneNode():

    def __init__(self, nodeid, log, manager, send_queue, callback_status, timeout = 0, name = ""):
        self._nodeid = nodeid
        self._xpl_manager = manager
        # Store if node is ready to receive or not
        self._status = False
        # Store if node has been seen recently or not
        self._up = True
        self._timeout_interval = timeout * 60 
        self._sniffer_queue = send_queue
        self._message_queue = deque()
        self.log = log
        self._name = ""
        self._last_timeout = 0
        self._callback_status = callback_status
        if name == "":
            self._name = "node"+str(nodeid)
        else:
            self._name = name
        self.log.info(u"*** Initialized BugoneNode for node %s with name %s and timeout %s***" % (str(nodeid), self._name, str(timeout)))
        if self._timeout_interval > 0:
            self._timeout_timer = XplTimer(60, self.timeout, manager)
            self._timeout_timer.start()
        #self._timeout = XplTimer(timeout, self.timeout, manager)

    def disable(self):
        #if self._timer_running:
        #    self._timeout.stop()
        self._status = False

    def init_timeout(self):
        if self._timeout_interval > 0:
            self._last_timeout = time.time()
            self.log.info("Last Timeout : %s" % str(self._last_timeout))
            if not self._up:
                self._up  = True
                self._callback_status(self._nodeid, True)

    def timeout(self):
        if (time.time() - self._last_timeout) > self._timeout_interval: 
            self.log.info("Last seen : %s" % str(time.time() - self._last_timeout))
            if self._up:
                self._up  = False
                self._callback_status(self._nodeid, False)
        else:
            if not self._up:
                self._up  = True
                self._callback_status(self._nodeid, True)

    def enable(self): 
        #if self._timer_running:
        #    self._timeout.stop()
        #self._timeout.start()
        self._status = True
        self.init_timeout()
        while len(self._message_queue) > 0:
            self._sniffer_queue.put(self._message_queue.popleft())

    def status(self):
        return self._status

    def send(self,message):
        """ Process message to send (already build)
        If available, send immediately, or store for later send
        """
        self.log.info(u"*** Node %s: Message to send: %s" % (str(self._nodeid), str(ord(message[3]))))
        if self._status:
            self.log.info(u"*** Node %s up, putting in the send queue ***" % str(self._nodeid))
            self._sniffer_queue.put(message)
        else:
            self.log.info(u"*** Node %s down, delaying message sending ***" % str(self._nodeid))
            self._message_queue.append(message)


class BugOne():

    def __init__(self, bugone_port, autoreconnect, log, cb_send_xpl, stop, registered_devices, managed_nodes, cb_register_thread, manager, fake_device = None):
        self.log = log
        self.stop = stop
        self.manager = manager

        # fake or real device
        self.fake_device = fake_device
        self.bugone_port = bugone_port
        self.autoreconnect = autoreconnect

        self.cb_send_xpl = cb_send_xpl
        self.cb_register_thread = cb_register_thread

        self.send_queue = Queue()

        # serial device
        self.registered_devices = registered_devices
        self.managed_nodes = managed_nodes
        self.bugone_opened = False
        self.open(self.stop())
#       self.bugone = serial.Serial(self.bugone_port, baudrate = 38400, timeout = 1)
        self._nodes = {}
        for i in self.managed_nodes:
            self._nodes[i] = BugOneNode(int(i),self.log,self.manager,self.send_queue,self.send_node_status, timeout = self.managed_nodes[i]["interval"],name = self.managed_nodes[i]["name"])



    def open(self,stop):
        """ Open the sniffer port
        if self.autoreconnect is set to True, we may not have the correct port
        number. We will need to look for existing ports with the same pattern. 
        Otherwise, only open and throw an exception if it doesn't work
        """
        try: 
            if self.autoreconnect:
                while not stop.isSet():
                    self.log.info("Attempting to connect to bugOne sniffer ...")
                    portlist = glob.glob(string.rstrip(self.bugone_port,"0123456789") + "*")
                    if not (portlist == []):
                        self.bugone_port = portlist[0]
                        self.log.info("Found new port with correct pattern: " + self.bugone_port)
                        time.sleep(1)
                        self.log.info("Reconnecting to sniffer...")
                        self.bugone = serial.Serial(self.bugone_port, baudrate = 38400, timeout = 1)
                        self.bugone_opened = True
                        self.log.info("Reconnection done! :)")
                        return
                    time.sleep(2)
            else:
                self.bugone = serial.Serial(self.bugone_port, baudrate = 38400, timeout = 1)
                self.bugone_opened = True
                self.connect_timer.stop()
        except:
            error = "Error while connecting to sniffer device: %s" % traceback.format_exc()
            self.log.error(u"{0}".format(error))
            self.bugone_opened = False
            return


    def listen(self, stop):
        """ Start listening to bugOne
        @param stop : an Event to wait for stop request
        """
        self.log.info(u"**** Start listening to bugOne network****")
        # infinite
        while True:
            try:
                while not stop.isSet():
                    if self.bugone_opened: 
                        self.read()
                    elif self.autoreconnect:
                        self.open(stop)
                    else:
                        return
                return
            except serial.SerialException:
                error = "Error while reading rfxcom device (disconnected ?) : %s" % traceback.format_exc()
                self.log.error(u"{0}".format(error))
                self.bugone_opened = False
                if self.autoreconnect:
                    self.open(stop)
                    continue
                else:
                    return

    def sender(self,stop):
        """ Sender thread function
        It waits on a Queue and send data as soon as the sniffer is ready and there is data to send
        """
        self.log.info(u"**** Start sender to bugOne network****")
        while True:
            try:
                while not stop.isSet():
                    message = self.send_queue.get(True)
                    self.log.info(u"***Message to send in the queue***")
                    if self.bugone_opened: 
                        self.send(message)
                    else:
                        self.log.error(u"Message to send, but no sniffer...")
                        return
                return
            except serial.SerialException:
                error = "Error while reading rfxcom device (disconnected ?) : %s" % traceback.format_exc()
                self.log.error(u"{0}".format(error))
                self.bugone_opened = False
                if self.autoreconnect:
                    self.open(stop)
                    continue
                else:
                    return

    def send(self, message):
        if len(message) > 255:
            raise Exception("Message is too long")
        self.log.info(u"***Sending message to sniffer: %s***" % str(ord(message[3])))
        sent = self.bugone.write(chr(len(message)) + message)
        self.log.info(u"***Sent %s chars***" % sent)
        self.bugone.flush()

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
        messageType = bugoneprotocol.getPacketType(message)
        srcNodeId = bugoneprotocol.getPacketSrc(message)
        destNodeId = bugoneprotocol.getPacketDest(message)
        counter = bugoneprotocol.getPacketCounter(message)
        self.log.info (u"Message [%s] from %s to %s" % (counter, hex(srcNodeId), hex(destNodeId)))
        if messageType == bugoneprotocol.PACKET_HELLO:
            self.log.info("Hello")
            self._update_status(srcNodeId,True)
        elif messageType == bugoneprotocol.PACKET_PING:
            self.log.info("Ping")
            self._update_status(srcNodeId,True)
        elif messageType == bugoneprotocol.PACKET_PONG:
            self.log.info("Pong")
            self._update_status(srcNodeId,True)
        elif messageType == bugoneprotocol.PACKET_VALUES:
            self._update_status(srcNodeId,True)
            values = bugoneprotocol.readValues(bugoneprotocol.getPacketData(message))
            for (srcDevice, destDevice, value) in values:
                self.log.info("- (%s.%s) -> (%s.%s) = %s" % \
                    (srcNodeId, srcDevice, destNodeId, destDevice, value))
                if (srcNodeId,srcDevice) in self.registered_devices:
                    dev = self.registered_devices[(srcNodeId,srcDevice)]
                    if dev["last_value"] != value:
                        dev["last_value"] = value
                        self.report_status(dev,value)
        elif messageType == PACKET_SLEEP:
            self.log.info("Sleep packet")
            self._update_status(srcNodeId,False)
        else:
            self.log.info([hex(ord(i)) for i in bugoneprotocol.getPacketData(message)])

    def _update_status(self,nodeid,status):
        if nodeid not in self._nodes:
            # Default timeout is 1hour
            self._nodes[nodeid] = BugOneNode(int(nodeid),self.log,self.manager,self.send_queue,self.send_node_status)
        if status: 
            if not self._nodes[nodeid].status():
                self.log.info(u"*** Node %s waking up...***" % nodeid)
            self._nodes[nodeid].enable()
        else:
            if self._nodes[nodeid].status():
                self.log.info(u"*** Node %s going to sleep...***" % nodeid)
            self._nodes[nodeid].disable()

    def send_node_status(self, nodeid, value): 
        if value: 
            cur = "high"
        else:
            cur = "low"
        self.cb_send_xpl(schema = "sensor.basic",
                data = {"device": self.managed_nodes[nodeid]["name"],
                    "type": "input",
                    "current": cur})
    def report_status(self, device, value):
        self.cb_send_xpl(schema = "sensor.basic", 
                data = {"device" : device["name"],
                    "type" : device["sensortype"],
                    "current" : float(value)/10})
