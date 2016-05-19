#!/usr/bin/env python
#md5sum="4073a1853651e1b430dfd24a51bc96fa"

from cli import cli
import re

got = cli('show logging last 1000')
server = re.findall('Script Server: (.*)\n', got)[-1]
fetch = 'copy http://%s:5000/api/config0/nxos run vrf management' % server

cli(fetch)
cli('copy run volatile:poap.conf')
cli('copy volatile:poap.conf scheduled-config')
cli('copy run start')

exit(0)
