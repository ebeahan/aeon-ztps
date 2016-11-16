#!/usr/bin/env bash

packer build -force ubuntu_64.json

cd output-vmware-iso
sh ../scripts/vmx-to-ova.sh -s .