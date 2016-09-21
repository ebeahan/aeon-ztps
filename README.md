# Aeon-ZTPS
Aeon-ZTPS is a universal Zero-Touch-Provisioning server for data center infrastructure systems.  Aeon-ZTPS was developed specifically to address the need for network engineers to bootstrap their datacenter switches without having to deal with the differences in the underlying NOS mechanisms.

Aeon-ZTPS runs as an Ubuntu 16.04LTS server using the Flask framework and a simple SQLite database.  The system provides both a REST/JSON API and a GUI.  The Aeon-ZTPS can optionally provide the DHCP service (included, but not enabled by default).

The complete documentation for Aeon-ZTPS can be found at *(readthedocs links to be provided later).

Questions? Comments? Please join us on *(system(s) to be named later)*

# Supported Systems
The initial release of the Aeon-ZTP server supports the following NOS/hardware:

| NOS | Hardware | Process |
|-----|----------|---------|
|Cisco NX-OS     | 9K and 3K models | [POAP](http://www.cisco.com/c/en/us/td/docs/switches/datacenter/nexus3000/sw/fundamentals/503_U3_1/b_Nexus_3000_Fundamentals_Guide_Release_503_U3_1/using_power_on_auto_provisioning.pdf)        |
|Arista EOS      | All models       | [Arista ZTP](https://eos.arista.com/ztp-set-up-guide/)        |
|Cumulus Linux   | All models       | [ONIE](http://onie.org/) and [Cumulus AutoProvisioning](https://docs.cumulusnetworks.com/display/DOCS/Zero+Touch+Provisioning+-+ZTP)        |

# Installation
If you are using VirtualBox, tou can build and install the Aeon-ZTP serverby invoking "vagrant up" from within the install directory after configuring the setup files.  For the complete details on the installation process, please <read the docs>

# Screenshots

*need to add a few screen shots of the GUI here*

# License
Apache 2.0
