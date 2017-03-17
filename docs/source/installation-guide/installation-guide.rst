Installation Guide
==================

This document outlines the steps required to build the Aeon-ZTPS from the files located in the github repository.
The total time required to build the Aeon-ZTPS could take some time (20m -> 1hr), depending on your existing installed
tools, and your connection speed to the Internet.  You can easily install Aeon-ZTPS into VirtualBox using the provided
Vagrant file in the install directory.  If you are not using VirtualBox, you can use the Ansible playbook file to
perform the installation process on any other Ubuntu 16.04 LTS system.

.. contents::
   :local:

.. |box| unicode:: ☐

.. |sp| unicode:: U+00A0

.. |br| raw:: html

   <br />


Install Setup Checklist
-----------------------
    |box| |sp| |sp| :strong:`Configure IP-addresses for the interfaces` |br|
        Edit the file :literal:`install/vars/interfaces.yml` and assign values specific to your environment.
        The default install is eth0 is the Vagrant/NAT interface, and eth1 is connected to the network infrastructure.

    .. figure:: install-interfaces.png


    :emphasis:`optional` |br|
    |box| |sp| |sp| :strong:`Enable DHCP Service` |br|

        Edit the file :literal:`install/vars/dhcp-server.yml` and change the :code:`DHCPS_enable` variable to
        :code:`yes`

    .. figure:: install-dhcp-yes.png

        Edit the file :literal:`install/vars/dhcp-server.yml` and set the values specific to your operational needs.
        The DHCP server only supports one NIC interface.  By default eth0 is the VirtualBox/NAT interface, and eth1
        is the interface intended to be connected to your network equipment.

    .. figure:: install-dhcpd.png

        If you want to make any changes to the DHCP server configuration file (template), edit the file
        :literal:`install/roles/dhcp-server/templates/dhcpd.conf`


Install via Vagrant
-------------------

.. _Vagrant: https://www.vagrantup.com/
.. _VirtualBox: https://www.virtualbox.org/wiki/Downloads/
.. _Ansible: http://docs.ansible.com/ansible/intro_installation.html/

The current installation process is designed to install the Aeon-ZTPS into a Vagrant environment using Vagrant and
an Ansible playbook.

The process uses a combination of the following tools, and associated versions.  This process has been verified using
a MacOS running Yosemite and ElCaptain.  If you are using a different set of
versions, you may run into issues.  Note that many of these versions are not the "latest", even at the time of
this writing.

    Vagrant_ |br|
        1.8.4 or later  — use "vagrant --version" to check
        You will need the Vagrant "vbguest" pluging installed.  To install, use: "vagrant plugin install vagrant-vbguest"

    VirtualBox_ |br|
        5.0.24, or later 5.0.x — use "VBoxManage --version" to check.  Note: For those running Mac OSX El Capital and
        needing a VirtualBox update, you may need to disable Apple's
        System Integrity Protection, as described `here <http://www.macworld
        .com/article/2986118/security/how-to-modify-system-integrity-protection-in-el-capitan.html>`__

    Ansible_ |br|
        version 2.0 or later   — use "ansible --version" to check.  Installation instructions are located `here
        <http://docs.ansible.com/ansible/intro_installation.html#latest-releases-on-mac-osx>`__.


Edit the :literal:`install/Vagrantfile` file to also assign the eth1 value as part of the Vagrant provision process.
    .. figure:: install-vagrantfile.png


To perform the build and installation into Vagrant, do the following on your host machine:

.. code:: bash

    cd install
    vagrant up

Once the VM build is complete, and the VM has been automatically rebooted, you can login to the VM by typing:

.. code:: bash

    vagrant ssh

----------
Login Info
----------
An account with username "admin" and password "admin" is created by default.


Install via Ansible Playbook
----------------------------
If you are not using VirtualBox, you can still use the same Ansible playbook to perform the installation process.
You will need to create an Ansible :emphasis:`hosts` file that contains the IP-address of your target system, or the
hostname if the IP-address is a known host via DNS.

For example, if your target host has the IP-address :literal:`192.168.59.254`, then your host file would look simply
like the following:

.. code-block:: yaml
   :caption: hosts

    192.168.59.254

Let's assume that the target host has an account call :literal:`admin`, and this user has sudo rights.  You would
then do the following to install Aeon-ZTPS on that server:

.. code:: bash

    cd install
    echo "192.168.59.265" > hosts
    ansible-playbook via-ansible.yml -i hosts -u admin -kK

Enable DHCP Service
-------------------
If you installed Aeon-ZTPS with the DHCP server disabled you can later enable the service.  From the Aeon-ZTPS
bash prompt you can run the following commands:

.. code:: bash

    sudo systemctl enable isc-dhcp-server
    sudo service isc-dhcp-server start

