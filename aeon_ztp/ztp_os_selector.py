
# Copyright 2014-present, Apstra, Inc. All rights reserved.
#
# This source code is licensed under End User License Agreement found in the
# LICENSE file at http://www.apstra.com/community/eula


import os
import yaml

_AEON_TOPDIR = os.getenv('AEON_TOPDIR')


def vendor_list():
    """ Returns a list of software currently supported by Aeon-ZTP server by name.

    Returns:
        list: List of software currently supported by Aeon-ZTP server by name.

    Examples:
        >>> print vendor_list()
        ['nxos', 'eos', 'cumulus']

    """
    return ['nxos', 'eos', 'cumulus']


def load_yaml(filename):
    """ Loads a YAML file from the filesystem and converts it to a usable python dictionary.

    Args:
        filename (str):

    Returns:
        dict: Python dictionary representation of given YAML filename.


    Raises:
        IOError: Raised if fucntion cannot load the filename


    """
    try:
        f = file(filename, 'r')
        data = yaml.load(f)
        return data
    except (IOError, OSError) as e:
        err = e[0]
        reason = e[1]
        error = 'load_yaml: Failed to open {filename}: {reason} {err}'.format(filename=filename, reason=reason, err=err)
        raise IOError(error)


def get(vendor):
    """ Loads a OS-Selector.cfg file by vendor name (eg: eos), loads it, and returns a python dictionary.

    Args:
        vendor (str): Vendor filename to search for

    Returns:
        dict: Dictionary representation of specified OS-selector configuration file for the specified vendor (eg: eos)

    """
    filename = os.path.join(_AEON_TOPDIR, 'etc/profiles/{vendor}/os-selector.cfg'.format(vendor=vendor))
    return load_yaml(filename)


class Vendor:
    """ Describes an Aeon-ZTP vendor specification, focusing on firmware locations

    Attributes:
        vendor (str): Name of the vendor (eg: eos)
        config_filename (str): Filesystem location of os-selector.cfg
        path (str): Filesystem location required to upload vendor files to
        image (str): Filesystem location of specific firmware file, eg /opt/downloads/eos/arista-3.4.swi
        check_firmware (bool): Checks if the expected firmware resides on the filesystem properly
        default_image (str): Default vendor image filename expected from os-selector.cfg
    """
    def __init__(self, vendor):
        """
        Args:
            vendor (str): Name of the vendor to search for (eg: eos)
        """
        self.vendor = vendor
        self.path = os.path.join(_AEON_TOPDIR, 'vendor_images/{vendor}'.format(vendor=vendor))
        self.config_filename = os.path.join(_AEON_TOPDIR, 'etc/profiles/{vendor}/os-selector.cfg'.format(vendor=vendor))
        try:
            _data = get(vendor)
            self.default_image = _data['default']['image']
            # self.default_version = _data['default']['exact_match']
            self.image = os.path.join(self.path, self.default_image)
            self.check_firmware = os.access(os.path.join(self.path, self.default_image), os.R_OK)
        except IOError:
            self.check_firmware = False
            self.default_image = "Missing Config"
