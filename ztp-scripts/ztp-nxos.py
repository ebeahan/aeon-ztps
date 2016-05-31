#!/usr/bin/env python
#md5sum="f0a9e86cd1ad585be6c554ae9e457b42"

from cli import cli
import re

got = cli("show logging last 1000")
server = re.findall("Script Server: (.*)\n", got)[-1]

cli("config ; ip host ztp-server {}".format(server))
cli("copy http://ztp-server:5000/api/config0/nxos run vrf management")

cli('copy run volatile:poap.conf')
cli('copy volatile:poap.conf scheduled-config')
cli('copy run start')

exit(0)
