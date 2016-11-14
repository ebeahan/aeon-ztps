#!/bin/bash
# Copyright 2014-present, Apstra, Inc. All rights reserved.
#
# This source code is licensed under End User License Agreement found in the
# LICENSE file at http://www.apstra.com/community/eula



REMOTE_USERNAME="admin"
REMOTE_PASSWD="admin"

INSTALL_LICENSE_FILE="license"
INSTALL_VRF_DEB="cl-mgmtvrf.deb"

LOCK_FILE=/mnt/persist/aeon-ztp.lock

# trap and print what failed
function error () {
    echo -e "ERROR: Script failed at $BASH_COMMAND at line $BASH_LINENO." >&2
    exit 1
}
trap error ERR


provision_url=$(grep -m1 'cumulus-provision-url' /var/lib/dhcp/dhclient.eth0.leases | awk -F "/" '{print $3}')
provision_ip=$(echo $provision_url | sed s/:.*$//g)

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
        cp -r /home/cumulus /home/${REMOTE_USERNAME}
        chown -R ${REMOTE_USERNAME}.${REMOTE_USERNAME} /home/${REMOTE_USERNAME}
        useradd --shell /bin/bash ${REMOTE_USERNAME}
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

function is_vrf_aware(){
    # Cumulus supports native VRF from version 3.x
    local cumulus_version=$(cat /etc/lsb-release | grep DISTRIB_RELEASE | cut -d= -f2)
    if [[ "${cumulus_version:0:1}" == "3" ]]; then
        return 0
    else
        return 1
    fi
}

function install_vrf_deb(){
    check=$(dpkg -l | grep -i cl-mgmtvrf)
    if [[ $? -eq 0 ]]
    then
        return
    fi

    wget -O cl-mgmtvrf.deb ${HTTP}/images/cumulus/${INSTALL_VRF_DEB}
    dpkg -i cl-mgmtvrf.deb
    /usr/sbin/cl-mgmtvrf --enable
    if [ -e /etc/cumulus/switchd.conf ]
    then
        sed -ri 's/#ignore_non_swps = FALSE/ignore_non_swps = TRUE/g' \
        /etc/cumulus/switchd.conf
    fi
}

function enable_mgmt_vrf(){
    if is_vrf_aware; then
            cat > /etc/network/interfaces << EOF
auto mgmt
iface mgmt
    address 127.0.0.1/8
    vrf-table auto
    post-up sudo service aos start

auto eth0
iface eth0 inet dhcp
    vrf mgmt
EOF
       ifreload -a
       ifdown eth0
       ifup eth0
       echo Waiting for $provision_ip to be reachable.
       counter=30
       until ping -c1 $provision_ip &>/dev/null; do
           sleep 1
           let counter-=1
           if [ $counter -lt 1 ]
           then
               echo "Unable to ping $provision_ip"
               exit 1
           fi
       done
    else
       install_vrf_deb
    fi
}

function kickstart_aeon_ztp(){
     wget -O /dev/null ${HTTP}/api/register/cumulus
}

create_remote_user
enable_mgmt_vrf
#install_license
kickstart_aeon_ztp

# CUMULUS-AUTOPROVISIONING

## exit cleanly, no reboot
exit 0