Cumulus Setup Guide
===================

This document describes information and usage of the Aeon-ZTPS system with the Cumulus Linux network operating
system.  At the time of this writing, Cumulus support has been tested with Cumulus version 2.x release, started
with 2.5.6. Cumulus 3.x support has not been tested.  This document is organized by the Aeon-ZTPS process stages,
as described in the Getting Started Guide.

.. contents::
   :local:

Device-ZTP
----------

ZTP-Script
~~~~~~~~~~
The DHCP server returns the cumulus-provision-url DHCP indicating how the switch can obtain the ZTP script.  By
default, this file is located in :literal:`downloads/ztp-cumulus.sh`.  If you've changed the DHCP server
configuration, you will need to update the location of this script accordingly.

The ZTP script, :literal:`ztp-cumulus.sh` is executed in the context of the Cumulus `AutoProvisioning <https://docs
.cumulusnetworks.com/display/DOCS/Zero+Touch+Provisioning+-+ZTP>`_ process.

* The following files are installed:
    * Cumulus License file
    * Cumulus VRF package file

.. warning::
    You must put your Cumulus license file on the Aeon-ZTPS in :literal:`downloads/cumulus/license`.
    If you want to change the location or filename, you will need to modify the :literal:`ztp-cumulus.sh` script file.

.. warning::
    You are responsible for providing a copy of the Cumulus VRF debian package.  You need to put this file on the
    Aeon-ZTPS in :literal:`vendor_images/cumulus/cl-mgmtvrf.deb`.  If you do not want to install the VRF package, or
    want to change the location/filename, you will need to modify the :literal:`ztp-cumulus.sh` script file.


* The :literal:`admin` account will be created with the password :literal:`admin`

At the end of the Cumulus AutoProvisioning process, the device will :strong:`NOT` reboot.

ZTP-Boot-Configuration
~~~~~~~~~~~~~~~~~~~~~~
At present, there is no Cumulus boot configuration files; applied as part of the the ZTP script execution.


Remote-Bootstrap
----------------

Static / Model Configuration
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

At present, there is no static configuration applied to the Cumulus device as part of the remote-bootstrap processing.

NOS Version Selection
~~~~~~~~~~~~~~~~~~~~~

The Aeon-ZTPS ships with a default NOS version selection configuration, located in
:literal:`etc/profiles/default/cumulus/os-selector.cfg`

.. code:: yaml

    #
    # 'default' means match hardware models not explicitly configured
    #
    default:
        regex_match: 2\.5\.[67]
        image: CumulusLinux-2.5.7-amd64.bin

The above configuration checks the running device to ensure that it is either 2.5.6 or 2.5.7.  If the device is not
running either of those version, then this file instructs Aeon-ZTPS to install the 2.5.7 image from the location:
:literal:`vendor_images/cumulus/CumulusLinux-2.5.7-amd64.bin`

If you want to change this configuration, you will need to modify this :literal:`os-selector.cfg` file and copy over
the necessary Cumulus software images.