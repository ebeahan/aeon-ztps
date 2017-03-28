#!/usr/bin/env bash

switch=$1
ssh admin@$switch <<'SSH'
#commands to run on remote host

sudo sed -i '/vrf mgmt/d' /etc/network/interfaces
sudo ztp -R
sudo reboot
'SSH'