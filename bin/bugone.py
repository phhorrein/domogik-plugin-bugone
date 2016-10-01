#!/usr/bin/python
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

BugOne integration in Domogik

Implements
==========

BugOneManager()

@author: Freki <freki@frekilabs.fr>
@copyright: (C) 2007-2013 Domogik project
@license: GPL(v3)
@organization: Domogik
"""

from domogik.xpl.common.xplmessage import XplMessage
from domogik.xpl.common.xplconnector import Listener
from domogik.xpl.common.plugin import XplPlugin

from domogik_packages.plugin_bugone.lib.bugone import BugOne
from domogik_packages.plugin_bugone.lib.bugone import BugOneException
import threading
import traceback

class BugOneManager(XplPlugin):
    """ Main class for BugOne Domogik plugin
    """

    def __init__(self):
        XplPlugin.__init__(self,name="bugone")

        ### Domogik part

        # If the plugin is not configured, we cannot start
        if not self.check_configured():
            return

        # Get the device list. We want the manager to run even if no devices are
        # found
        self.devices = self.get_device_list(quit_if_no_device = False)
        self.interval = self.get_config("interval")
        self.bugone_port = self.get_config("bugone_port")
        self.autoreconnect = self.get_config("bugone_reconnect")

        # Initialize device dictionnary (for reverse search, when receiving data
        # from bugone, to which device must be signalled)

        self.existing_devices = {}

        for dev in self.devices:
            try: 
                nodeid = self.get_parameter(dev,"nodeid")
                devid = self.get_parameter(dev,"devid")
                """ Get first feature key 
                This is used to get the name of the device: it is stored in the
                features, but common between them
                """
                feat = dev['xpl_stats'].iterkeys().next()
                name = self.get_parameter_for_feature(dev,"xpl_stats",feat,"device")
                """ Get name for first feature
                Devices in bugOne plugin are either simple value devices or
                management devices. Management devices are known and will not
                use this parameter
                """
                # Get name for the first feature. 
                sensortype = self.get_parameter_for_feature(dev,"xpl_stats",feat,"type")
                self.existing_devices[(nodeid,devid)] = { "name" : name, "sensortype": sensortype }

                self.log.info("Device id " + str(devid) + " at node " + str(nodeid))

            except:
                self.log.error(traceback.format_exc())

        # Initialize bugOne manager

        self.bugOne_manager = BugOne(self.bugone_port,self.autoreconnect,self.log, self.send_xpl,self.get_stop,self.existing_devices,self.register_thread, self.myxpl)

        self.recv_thread = threading.Thread(None, self.bugOne_manager.listen,"bugone_listen",(self.get_stop(),), {})

        self.register_thread(self.recv_thread)
        self.recv_thread.start()
        self.ready()
        self.log.info("Plugin ready :)")

    def send_xpl(self, message = None, schema = None, data = {}):
        """ Send xPL message on network
            Copied from RFXCom implementation
        """
        if message != None:
            self.log.debug(u"send_xpl : send full message : {0}".format(message))
            self.myxpl.send(message)

        else:
            self.log.debug(u"send_xpl : Send xPL message xpl-trig : schema:{0}, data:{1}".format(schema, data))
            msg = XplMessage()
            msg.set_type("xpl-trig")
            msg.set_schema(schema)
            for key in data:
                msg.add_data({key : data[key]})
            self.myxpl.send(msg)



if __name__ == "__main__":
    BugOneManager()
