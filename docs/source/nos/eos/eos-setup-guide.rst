Arista EOS Setup Guide
======================

This document describes information and usage of the Aeon-ZTPS system with the Arista EOS network operating system.
This document is organized by the Aeon-ZTPS process stages, as described in the Getting Started Guide.

.. contents::
   :local:

Device-ZTP
----------

ZTP-Script
~~~~~~~~~~

The DHCP server returns the :literal:`bootfile-name` DHCP option the name of the ZTP script.  By default, this file is
located in :literal:`tftpboot/ztp-eos.sh`.  If you've changed the DHCP server configuration, you will need to update
the location of this script accordingly.  The ZTP script is a Bash script.

The ZTP script is executed in the context of the Arista `ZeroTouchProvisioning <https://eos.arista
.com/ztp-set-up-guide/>`_ process:

* Install the contents of the :literal:`eos-boot.conf` file from Aeon-ZTPS
* Statically assign the IP-address / gateway information obtained from DHCP
* Assign the :literal:`Ma1` interface into a VRF called :emphasis:`management`
* Signals the Aeon-ZTPS for remote-bootstrap

Once the Arista device completes the EOS ZeroTouchProvisioning process, the device will :strong:`NOT` reboot.

ZTP-Boot-Configuration
~~~~~~~~~~~~~~~~~~~~~~

The EOS boot configuration file is located at :literal:`etc/configs/eos/eos-boot.conf`.  The primary purpose of this
configuration is to enable remote management via the eAPI over HTTP.  Aeon-ZTPS will access the device
using the hardcoded user=admin, password=admin.

Remote-Bootstrap
----------------

Static / Model Configuration
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The Arista EOS static configuration files are located in the :literal:`etc/configs/eos directory`.  The file
:literal:`all.conf`, if exists, will be first applied to all device models.  Then if a model specific file exists it
will be applied.

The model value is taken from the output of :emphasis:`"show version"`, the JSON field :literal:`modelName`.  The
resulting model-specific filename would be :emphasis:`<modelName>.conf`.  For example, the following device would yield
the Aeon-ZTPS to look for a file called: :literal:`etc/configs/eos/DCS-7050QX-32-F.conf` using the :literal:`modelName`
value indicated on line 3.

.. code-block:: bash
   :linenos:

    switch>show version | json
    {
        "modelName": "DCS-7050QX-32-F",
        "internalVersion": "4.15.1F-2483969.4151F",
        "systemMacAddress": "44:4c:a8:0c:b9:e1",
        "serialNumber": "JPE15244110",
        "memTotal": 3978212,
        "bootupTimestamp": 1473477510.75,
        "memFree": 691888,
        "version": "4.15.1F",
        "architecture": "i386",
        "internalBuildId": "15807785-bb32-41c0-ac34-a7b504427d22",
        "hardwareRevision": "02.11"
    }

NOS Version Selection
~~~~~~~~~~~~~~~~~~~~~

The Aeon-ZTPS ships with a default NOS version selection configuration, located in
:literal:`etc/profiles/default/eos/os-selector.cfg`

.. code-block:: yaml

    #
    # 'default' means match hardware models not explicitly configured
    #
    default:
        exact_match: 4.15.1F
        image: EOS-4.15.1F.swi

The above configuration checks the running device to ensure that is running :emphasis:`4.15.1F`.  If the device is not
running that exact version, then this file instructs Aeon-ZTPS to install the that image from the location:
:literal:`vendor_images/eos/EOS-4.15.1F.swi`

If you want to change this configuration, you will need to modify this :literal:`os-selector.cfg` file and copy over
the necessary Arista software images.
