#!/bin/sh

sudo apt-get update

sudo apt-get install -y build-essential python-dev
sudo apt-get install -y python-pip
sudo apt-get install -y libxml2-dev libxslt-dev zlib1g-dev

sudo apt-get -y install rabbitmq-server
sudo apt-get -y install postgresql postgresql-contrib
sudo apt-get install -y xinetd tftpd tftp

sudo mkdir -p /tftpboot
sudo chmod -R 777 /tftpboot
sudo chown -R nobody /tftpboot

##
## cd into the Aeon ZTP mounted area and copy / install
## the necessary files
##

cd /aeon-ztp
sudo pip install -r requirements.txt
sudo cp ztp-scripts/ztp-nxos.py /tftpboot
sudo cp ztp-scripts/poap-md5sum /tftpboot

##
## now restart xinetd to startup TFTP server
##

sudo cp tftpd/tftp /etc/xinet.d
sudo service xinetd restart

exit 0