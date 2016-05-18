#!/bin/env python
#md5sum="d3872a8829cd2bfe10252fad4b2785d5"

from cli import *
cli('conf ; feature bash')
cli('conf ; feature nxapi')
cli('conf ; feature scp-server')
cli('conf ; username admin password 5 $1$Yg5kzRKD$u4LwnU8eFYRpyz/3LMF1d/  role network-admin')
cli('conf ; no password strength-check')
cli('conf ; ip domain-lookup')
cli('conf ; service unsupported-transceiver')
cli('copy run volatile:poap.conf')
cli('copy volatile:poap.conf scheduled-config')
cli('copy run start')
exit(0)