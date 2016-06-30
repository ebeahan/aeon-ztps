#!/bin/bash

## trap and print what failed

function error () {
    echo -e "ERROR: Script failed at $BASH_COMMAND at line $BASH_LINENO." >&2
    exit 1
}
trap error ERR

SERVER_PORT="8080"
SERVER=$(grep -m 1 dhcp-server /var/lib/dhcp/dhclient.eth0.leases | awk '{ print $3 }' | tr --delete ';')

HTTP="http://${SERVER}:${SERVER_PORT}"

echo ""
echo "-------------------------------------"
echo "Aeon-ZTP auto-provision from: ${HTTP}"
echo "-------------------------------------"
echo ""

function set_cumulus_passwd(){
   usermod -p $(echo $1 | openssl passwd -1 -stdin) cumulus
}

function install_license(){
   /usr/cumulus/bin/cl-license -i ${HTTP}/downloads/cumulus/license
}

function install_vrf(){
    wget -O cl-mgmtvrf.deb ${HTTP}/images/cumulus/cl-mgmtvrf.deb
    dpkg -i cl-mgmtvrf.deb
    /usr/sbin/cl-mgmtvrf --enable
    if [ -e /etc/cumulus/switchd.conf ]
    then
        sed -ri 's/#ignore_non_swps = FALSE/ignore_non_swps = TRUE/g' \
        /etc/cumulus/switchd.conf
    fi
}

function kickstart_aeon_ztp(){
    wget -O /dev/null ${HTTP}/api/register/cumulus
}

set_cumulus_passwd "admin"
install_vrf
install_license
kickstart_aeon_ztp

reboot

# CUMULUS-AUTOPROVISIONING
## exit cleanly

exit 0

