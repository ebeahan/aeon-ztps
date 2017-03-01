Cisco NX-OS Setup Guide
=======================

This document describes information and usage of Aeon-ZTPS with the Cisco NX-OS network operating system
for the 9K and 3K product model families.  This document is organized by the Aeon-ZTPS process stages, as described
in the Getting Started Guide.

.. contents::
   :local:

Device-ZTP
----------

ZTP-Script
~~~~~~~~~~

The DHCP server returns the :literal:`bootfile-name` DHCP option the name of the ZTP script.  By default, this file is
located in :literal:`tftpboot/ztp-nxos.py`.  If you've changed the DHCP server configuration, you will need to update
the location of this script accordingly. This script is written in Python.

The ZTP script is executed in the context of the Cisco POAP process:

    * Install the contents of the :literal:`nxos-boot.conf` file from Aeon-ZTPS
    * Sets up the scheduled-config to be executed on next reboot
    * Signals the Aeon-ZTPS for remote-bootstrap

Once the Cisco device completes the POAP process, the device :strong:`WILL` reboot.

.. warning::
    If you change the ztp-nxos.py file for any reason, you MUST run the script :emphasis:`poap-md5sum
    ztp-nxos.py` to regenerate the MD5 checksum value that is located at the top of the ztp-nxos.py file.  This
    poap-md5sum script is also located in the :literal:`tftpboot` directory


ZTP-Boot-Configuration
~~~~~~~~~~~~~~~~~~~~~~

The NX-OS boot configuration file is located at :literal:`etc/configs/nxos/nxos-boot.conf`.  The primary purpose of
this configuration is to enable remote management via the NXAPI over HTTP.  Aeon-ZTPSwill access the device
using the hardcoded user=admin, password=admin.

Remote-Bootstrap
----------------

Static / Model Configuration
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The Cisco NX-OS static configuration files are located in the :literal:`etc/configs/nxos` directory.  The file
:literal:`all.conf`, if exists, will be first applied to all device models.  Then if a model specific file exists it
will be applied.

The model value is taken from the output of :emphasis:`show hardware` from the :strong:`Switch hardware ID` block of
output (as shown on line 9 below). The resulting model-specific filename would be :emphasis:`<model>.conf`.  For
example, the following device would yield Aeon-ZTPS to look for a file called:
:literal:`etc/configs/nxos/N9K-C9396PX.conf`

.. code-block:: text
   :linenos:

    switch> show hardware
    ...
    --------------------------------
    Switch hardware ID information
    --------------------------------

    Switch is booted up
      Switch type is : Nexus9000 C9396PX Chassis
      Model number is N9K-C9396PX
      H/W version is 2.2
      Part Number is 73-15605-04
      Part Revision is D0
      Manufacture Date is Year 2014 Week 42
      Serial number is ABCD12345
      CLEI code is CMMPE00DRB


NOS Version Selection
~~~~~~~~~~~~~~~~~~~~~

Aeon-ZTPS ships with a default NOS version selection configuration, located in
:literal:`etc/profiles/default/nxos/os-selector.cfg`

.. code-block:: yaml

    #
    # 'default' means match hardware models not explicitly configured
    #
    default:
        exact_match: 7.0(3)I2(2d)
        image: nxos.7.0.3.I2.2d.bin

The above configuration checks the running device to ensure that is running :emphasis:`7.0(3)I2(2d)`.  If the device is
not running that specific version, then this file instructs Aeon-ZTPS to install the that image from the
location: :literal:`vendor_images/nxos/nxos.7.0.3.I2.2d.bin`

If you want to change this configuration, you will need to modify this :literal:`os-selector.cfg` file and copy over
the necessary Cisco NX-OS software images.
