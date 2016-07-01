#!/bin/bash

## trap and print what failed

function error () {
    echo -e "ERROR: Script failed at $BASH_COMMAND at line $BASH_LINENO." >&2
    exit 1
}
trap error ERR

LOCK_FILE=/mnt/persist/aeon-ztp.lock


SERVER_PORT="8080"
SERVER=$(grep -m 1 dhcp-server /var/lib/dhcp/dhclient.eth0.leases | awk '{ print $3 }' | tr --delete ';')

HTTP="http://${SERVER}:${SERVER_PORT}"

echo ""
echo "-------------------------------------"
echo "Aeon-ZTP auto-provision from: ${HTTP}"
echo "-------------------------------------"
echo ""

function setup_user_cumulus(){
    if [[ ! -e /etc/sudoers.d/cumulus ]]
    then
        usermod -p $(echo $1 | openssl passwd -1 -stdin) cumulus
        echo "cumulus ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/cumulus
    fi
}

function install_license(){
   cl_lic=/usr/cumulus/bin/cl-license
   lic=$($cl_lic)
   if [[ $? -ne 0 ]]
   then
      $cl_lic -i ${HTTP}/downloads/cumulus/license && service switchd restart
   fi
}

function install_vrf(){
    check=$(dpkg -l | grep -i cl-mgmtvrf)
    if [[ $? -eq 0 ]]
    then
        return
    fi

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
    if [[ ! -e $LOCK_FILE ]]
    then
        wget -O /dev/null ${HTTP}/api/register/cumulus
        touch $LOCK_FILE
    else
        rm $LOCK_FILE
    fi
}

setup_user_cumulus "admin"
install_vrf
install_license
kickstart_aeon_ztp

# CUMULUS-AUTOPROVISIONING

## exit cleanly, no reboot
exit 0

