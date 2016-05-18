#!/usr/bin/env python
#md5sum="d3872a8829cd2bfe10252fad4b2785d5"

from cli import *

cli('copy http://172.20.80.10:5000/api/config0/nxos run vrf management')
cli('copy run volatile:poap.conf')
cli('copy volatile:poap.conf scheduled-config')
cli('copy run start')

exit(0)