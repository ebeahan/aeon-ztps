#!/usr/bin/env python
#md5sum="47914a8888970d4ec369f466cbc6b125"

from cli import cli
import re

got = cli("show logging last 1000")
server = re.findall("Script Server: (.*)\n", got)[-1]

cli("config ; ip host ztp-server {}".format(server))
cli("copy http://ztp-server:5000/api/config0/nxos run vrf management")

cli('copy run volatile:poap.conf')
cli('copy volatile:poap.conf scheduled-config')
cli('copy run start')

# this copy triggers the register and kicks off the background
# ZTP bootstrap process on the server.

cli("copy http://ztp-server:5000/api/register/nxos volatile: vrf management")

exit(0)
