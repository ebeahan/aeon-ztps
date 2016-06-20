#!/bin/bash

# Extract the Aeon ZTP server IP address from /var/log/messages.
# Hardcode the Aeon ZTP server port-number

SERVER=$(sudo awk '/CONFIG_DOWNLOAD:/ {print $NF}' /var/log/messages | cut --delimiter=/ -f3)
SERVER_PORT=8080

HTTP="http://${SERVER}:${SERVER_PORT}"
HTTP_DL="${HTTP}/downloads"
HTTP_API="${HTTP}/api"

## trap and print what failed

function error () {
    echo -e "ERROR: Script failed at $BASH_COMMAND at line $BASH_LINENO." >&2
    exit 1
}
trap error ERR

# These scripts function to setup the management IP address in the configuration
# file based on the DHCP response.  The /var/log/messages file contains this
# information as well, so we could remove these scripts if we extract the
# values from the /var/log/messages file.  TODO

sudo wget -O /mnt/flash/eos_dhcp_script ${HTTP_DL}/eos/eos_dhcp_script
sudo wget -O /mnt/flash/dhcp_intf_script ${HTTP_DL}/eos/dhcp_intf_script
sudo wget -O /mnt/flash/promisc_ma1_script ${HTTP_DL}/eos/promisc_ma1_script

sudo wget -O /mnt/flash/startup-config ${HTTP_API}/bootconf/eos
sudo reboot
