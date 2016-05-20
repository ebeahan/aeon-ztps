#!/usr/bin/env python
#md5sum="c2192282d3425f6afc76a18927355cff"

from cli import cli
import re

got = cli("show logging last 1000")
server = re.findall("Script Server: (.*)\n", got)[-1]

cli("copy http://{}:5000/api/config0/nxos run vrf management".format(server))
cli("config ; ip host ztp-server {}".format(server))

cli("run bash sudo sed -i \'s|\(^Defaults *requiretty\)|#\1|g\' "
    "/isan/vdc_1/virtual-instance/guestshell+/rootfs/etc/sudoers 2>&1")

cli('copy run volatile:poap.conf')
cli('copy volatile:poap.conf scheduled-config')
cli('copy run start')

exit(0)
