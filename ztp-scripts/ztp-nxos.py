#!/usr/bin/env python
#md5sum="db9bc9ddaa2a06a02e3433abc6cd442b"

from cli import cli
import re

# get the ZTP server IP address from the logs.  no other way right now

got = cli("show logging last 1000")
server = re.findall("Script Server: (.*)\n", got)[-1]
server = "%s:5000" % server

# copy the basic config to enable remote management. all other ZTP
# tasks will be initiated by the ZTP server

cli("copy http://%s/api/config0/nxos run vrf management" % server)
cli('copy run volatile:poap.conf')
cli('copy volatile:poap.conf scheduled-config')

# this copy triggers the register and kicks off the background
# ZTP bootstrap process on the server.

cli("copy http://%s/api/register/nxos volatile: vrf management" % server)

exit(0)
