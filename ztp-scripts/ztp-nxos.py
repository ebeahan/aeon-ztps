#!/usr/bin/env python
#md5sum="27e5dba9d3de6a7334892c48cdba2ff2"

from cli import cli
import re

got = cli("show logging last 1000")
server = re.findall("Script Server: (.*)\n", got)[-1]

cli("copy http://{}:5000/api/config0/nxos run vrf management".format(server))
cli("config ; ip host ztp-server {}".format(server))

cli('copy run volatile:poap.conf')
cli('copy volatile:poap.conf scheduled-config')
cli('copy run start')

exit(0)
