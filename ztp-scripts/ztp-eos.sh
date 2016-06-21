#!/bin/bash

## trap and print what failed

function error () {
    echo -e "ERROR: Script failed at $BASH_COMMAND at line $BASH_LINENO." >&2
    exit 1
}
trap error ERR

# Extract the Aeon ZTP server IP address from /var/log/messages.
# Hard code the Aeon ZTP server port-number

SERVER_PORT=8080


DHCP_SUCCESS=$(grep -m1 DHCP_SUCCESS /var/log/messages)

# example output:
# ---------------
# Jun 21 13:28:07 localhost ZeroTouch: %ZTP-5-DHCP_SUCCESS: DHCP response received on Management1
# [ Ip Address: 172.20.68.50/24; Gateway: 172.20.68.1; Boot File: tftp://172.20.68.4/ztp-eos.sh ]

INTF=$(echo ${DHCP_SUCCESS} | gawk 'match($0, /received on ([^ ]+)/,arr){ print arr[1]}')
IP_ADDR=$(echo ${DHCP_SUCCESS} | gawk 'match($0, /Ip Address: ([^;]+)/,arr){ print arr[1]}')
GATEWAY=$(echo ${DHCP_SUCCESS} | gawk 'match($0, /Gateway: ([^;]+)/,arr){ print arr[1]}')
BOOTFILE=$(echo ${DHCP_SUCCESS} | gawk 'match($0, /Boot File: ([^ ]+)/,arr){ print arr[1]}')

SERVER=$(echo ${BOOTFILE} | cut --delimiter=/ -f3)

HTTP="http://${SERVER}:${SERVER_PORT}"
HTTP_DL="${HTTP}/downloads"
HTTP_API="${HTTP}/api"

wget -O /dev/null ${HTTP_API}/register/eos

CLI="FastCli -p15 -c"

${CLI} "enable
copy ${HTTP_API}/bootconf/eos running"

${CLI} "configure terminal
ip route vrf management 0.0.0.0/0 $GATEWAY
interface $INTF
vrf forwarding management
ip address $IP_ADDR"

${CLI} "copy run start"

exit 0
