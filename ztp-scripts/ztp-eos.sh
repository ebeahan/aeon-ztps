#!/bin/bash
# Copyright 2014-present, Apstra, Inc. All rights reserved.
#
# This source code is licensed under End User License Agreement found in the
# LICENSE file at http://www.apstra.com/community/eula


CLI="FastCli -p15 -c"

## trap and print what failed

function error () {
    echo -e "ERROR: Script failed at $BASH_COMMAND at line $BASH_LINENO." >&2
    exit 1
}
trap error ERR

# -------------------------------------------------------------------
# for now, hard code the Aeon ZTP server port-number.  future release
# will dynamically set this value
# -------------------------------------------------------------------

SERVER_PORT=8080

# ----------------------------------------------------
# Use the ZTP DHCP options to configure the management
# interface of the device as well as know the ip-addr
# of the Aeon ZTP server
# ----------------------------------------------------

DHCP_SUCCESS=$(grep -m1 DHCP.*_SUCCESS /var/log/messages)
NAME_SERVER=$(grep -m1 nameserver /var/log/messages)

# example output:
# ---------------
# Jun 21 13:28:07 localhost ZeroTouch: %ZTP-5-DHCP_SUCCESS: DHCP response received on Management1
# [ Ip Address: 172.20.68.50/24; Gateway: 172.20.68.1; Boot File: tftp://172.20.68.4/ztp-eos.sh ]

INTF=$(echo ${DHCP_SUCCESS} | gawk 'match($0, /received on ([^ ]+)/,arr){ print arr[1]}')
GATEWAY=$(echo ${DHCP_SUCCESS} | gawk 'match($0, /Gateway: ([^;]+)/,arr){ print arr[1]}')
BOOTFILE=$(echo ${DHCP_SUCCESS} | gawk 'match($0, /Boot File: ([^ ]+)/,arr){ print arr[1]}')
DNS_IP=$(echo ${NAME_SERVER} | gawk 'match($0, /nameserver ([^ ]+)#/,arr){
print arr[1]}')

SERVER=$(echo ${BOOTFILE} | cut --delimiter=/ -f3)

HTTP="http://${SERVER}:${SERVER_PORT}"
HTTP_DL="${HTTP}/downloads"
HTTP_API="${HTTP}/api"

# IP Address will be split in IP and subnet, also to workaround an issue with EOS 4.20.1
# where subnet is repeated twice by mistake(e.g. 172.20.111.3/24/24)
IP_ADDR_FULL=$(echo ${DHCP_SUCCESS} | gawk 'match($0, /Ip Address: ([^;]+)/,arr){ print arr[1]}')
IP_ADDR="$(echo $IP_ADDR_FULL | cut -d/ -f1)"
SUBNET="$(echo $IP_ADDR_FULL | cut -d/ -f2)"

${CLI} "enable"
${CLI} "show version > version_info"

if grep vEOS /mnt/flash/version_info; then
    ${CLI} "copy ${HTTP_DL}/eos/promisc_ma1_script flash:"
    ${CLI} "copy ${HTTP_DL}/eos/promisc_ma1_event running"
fi

${CLI} "copy ${HTTP_API}/bootconf/eos running"

# -------------------------------------------------------------------
# kick-off the Aeon ZTP server bootstrap process.
# MUST be done before updating the EOS configuration
# -------------------------------------------------------------------

wget -O /dev/null ${HTTP_API}/register/eos

# ----------------------------------------------
# update the EOS management configuration
# ----------------------------------------------
if [[ -n "$GATEWAY" ]]; then
${CLI} "configure terminal
ip route 0.0.0.0/0 $GATEWAY"
fi

if [[ -n "$DNS_IP" ]]; then
${CLI} "configure terminal
ip name-server $DNS_IP"
fi

${CLI} "configure terminal
interface $INTF
ip address $IP_ADDR/$SUBNET"

${CLI} "copy run start"

reboot
