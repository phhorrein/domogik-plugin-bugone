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

#from domogik_packages.plugin_bugone.lib.bugone import Bugone
#from domogik_packages.plugin_bugone.lib.bugone import BugoneException
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

        # Initialize device dictionnary (for reverse search, when receiving data
        # from bugone, to which device must be signalled)

        self.existing_devices = {}

        for dev in self.devices:
            try: 
                nodeid = self.get_parameter(dev,"nodeid")
                devid = self.get_parameter(dev,"devid")

                self.existing_devices[(nodeid,devid)] = dev

                self.log.info("Device id " + str(devid) + " at node " + str(nodeid))

            except:
                self.log.error(traceback.format_exc())

        # Initialize bugOne manager

#        self.bugOne_manager = BugOne()

#        self.recv_thread = threading.Thread(None, bugOne.listen,"recv",(self.get_stop(),), {})

        self.ready()
        self.log.info("Plugin ready :)")



if __name__ == "__main__":
    BugOneManager()
