DIY Wireless Bug: Domogik plugin
================

The bugOne is a small low-power DIY board designed to create low-power wireless
sensors or actuators. It's an open source, open hardware project. You can find
all sources here: https://github.com/jkx/DIY-Wireless-Bug

This is a domogik plugin designed to make the bugOne boards visible from
Domogik. It implements a bridge to the bugOne protocol and manages all "connected"
boards. It creates all associated Domogik modules (or it makes use of generic
one when possible). 

Please note that in order to be fully integrated, the bugOne boards should
provide the "boardinfo" device with devid 254. This device provides standardized
information on what is available on the board. It allows automatic detection of
available sensors and actuators. 

Please note that this plugin is experimental, and will stay experimental as long
as the user base stays low (bugOne is not a popular project). 

More information on how the plugin can be used is found in the plugin documentation. 


