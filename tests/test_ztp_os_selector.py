from tempfile import NamedTemporaryFile
from mock import patch
import yaml
import pytest
import os

from aeon_ztp import ztp_os_selector

topdir = '/opt/aeonztps/'
ztp_os_selector._AEON_TOPDIR = topdir


def test_vendor_list():
    expected_vendor_list = ['nxos', 'eos', 'cumulus']
    vendor_list = ztp_os_selector.vendor_list()
    assert vendor_list == expected_vendor_list


def test_load_yaml():
    tf = NamedTemporaryFile()
    data = {'test_key': 'test_value'}
    tf.write(yaml.dump(data))
    tf.flush()
    test_yaml = ztp_os_selector.load_yaml(tf.name)
    assert test_yaml == data


@patch('aeon_ztp.ztp_os_selector.yaml.load')
def test_load_yaml_exception(mock_yaml):
    mock_yaml.side_effect = IOError()
    with pytest.raises(IOError):
        ztp_os_selector.load_yaml('filename')


@patch('aeon_ztp.ztp_os_selector.load_yaml')
def test_get(mock_load_yaml):
    vendor = 'test_vendor'
    filename = os.path.join(topdir, 'etc/profiles/{vendor}/os-selector.cfg'.format(vendor=vendor))
    ztp_os_selector.get(vendor)
    mock_load_yaml.assert_called_with(filename)


def test_vendor_missing_config():
    vname = 'test_vendor'
    v = ztp_os_selector.Vendor(vname)
    assert not v.check_firmware
    assert v.default_image == 'Missing Config'


@patch('aeon_ztp.ztp_os_selector.os.access', return_value=True)
@patch('aeon_ztp.ztp_os_selector.get')
def test_vendor(mock_get, mock_os_access):
    default_image = 'test_image'
    data = {'default': {'image': default_image}}
    mock_get.return_value = data
    vendor = 'test_vendor'
    path = os.path.join(topdir, 'vendor_images/{vendor}'.format(vendor=vendor))
    v = ztp_os_selector.Vendor(vendor)
    assert v.config_filename == os.path.join(topdir,
                                             'etc/profiles/{vendor}/os-selector.cfg'.format(vendor=vendor))
    assert v.path == path
    assert v.image == os.path.join(path, default_image)
    assert v.check_firmware
    assert v.default_image == default_image
    assert v.vendor == vendor
