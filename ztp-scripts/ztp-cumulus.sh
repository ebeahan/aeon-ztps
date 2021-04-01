#!/bin/bash
# Copyright 2014-present, Apstra, Inc. All rights reserved.
#
# This source code is licensed under End User License Agreement found in the
# LICENSE file at http://www.apstra.com/community/eula



REMOTE_USERNAME="admin"
REMOTE_PASSWD="admin"

INSTALL_LICENSE_FILE="license"

LOCK_FILE=/mnt/persist/aeon-ztp.lock

# trap and print what failed
function error () {
    echo -e "ERROR: Script failed at $BASH_COMMAND at line $BASH_LINENO." >&2
    exit 1
}
trap error ERR


provision_url=$(cat /var/lib/dhcp/dhclient.eth0.leases | grep 'cumulus-provision-url'| tail -1 | awk -F "/" '{print $3}')
if [ -n "$provision_url" ]; then
    HTTP="http://${provision_url}"
else
    echo "Missing cumulus-provision-url" >&2
    exit 1
fi

echo ""
echo "-------------------------------------"
echo "Aeon-ZTP auto-provision from: ${HTTP}"
echo "-------------------------------------"
echo ""

function create_remote_user(){
    sudoer_file=/etc/sudoers.d/${REMOTE_USERNAME}

    if [[ ! -e ${sudoer_file} ]]
    then
        adduser --disabled-password --gecos "" ${REMOTE_USERNAME}
        usermod -p $(echo ${REMOTE_PASSWD} | openssl passwd -1 -stdin) ${REMOTE_USERNAME}
        echo "${REMOTE_USERNAME} ALL=(ALL) NOPASSWD:ALL" > ${sudoer_file}
    fi
}

function install_license(){
   cl_lic=/usr/cumulus/bin/cl-license
   if [[ ! -x ${cl_lic} ]]; then
     return
   fi

   lic=$(${cl_lic})
   if [[ $? -ne 0 ]]
   then
      ${cl_lic} -i ${HTTP}/downloads/cumulus/${INSTALL_LICENSE_FILE} && service switchd restart
   fi
}

function is_cumulus_vx(){
   local product=$(decode-syseeprom | grep "Product Name" | awk '{print $NF}')
   if [[ "$product" == "VX" ]]; then
      return 0
   else
      return 1
   fi
}

function kickstart_aeon_ztp(){
     wget -O /dev/null ${HTTP}/api/register/cumulus
}

create_remote_user
kickstart_aeon_ztp

if ! is_cumulus_vx; then
   install_license
fi

# CUMULUS-AUTOPROVISIONING

# exit cleanly, no reboot
exit 0
