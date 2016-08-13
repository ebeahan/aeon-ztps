#!/usr/bin/env python
# Copyright 2014-present, Apstra, Inc. All rights reserved.
#
# This source code is licensed under End User License Agreement found in the
# LICENSE file at http://www.apstra.com/community/eula

#md5sum="0cf4274e0a79bdd6acf0bffdb12275fa"

from cli import cli
import re

# get the ZTP server IP address from the logs.  no other way right now
SERVER_PORT = 8080

server = re.findall("Script Server: (.*)\n", cli("show logging last 1000"))[-1]
server = "{}:{}".format(server, SERVER_PORT)

# get the loaded image file name

image_file = re.findall("image file is: (.*)\n", cli("show hardware"))[-1]

# copy the basic config to enable remote management. all other ZTP
# tasks will be initiated by the ZTP server

cli("copy http://%s/api/bootconf/nxos run vrf management" % server)
cli("conf t ; boot nxos %s" % image_file)

cli('copy run volatile:poap.conf')
cli('copy volatile:poap.conf scheduled-config')
cli('copy run start')

# this copy triggers the register and kicks off the background
# ZTP bootstrap process on the server.

cli("copy http://%s/api/register/nxos volatile: vrf management" % server)

exit(0)
