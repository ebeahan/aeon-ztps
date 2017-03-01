import os
import yaml
import tempfile
import pytest
import json
import sys
import copy
from aeon_ztp.bin import aztp_os_selector
from collections import namedtuple

g_dev_data = {
    'os_name': 'cumulus-vx',
    'vendor': 'cumulus',
    'hw_part_number': '1234',
    'hostname': 'cumulus',
    'fqdn': 'cumulus.localhost',
    'virtual': True,
    'service_tag': '1234',
    'os_version': '3.1.1',
    'hw_version': '1234',
    'mac_address': '0123456789012',
    'serial_number': '09786554',
    'hw_model': 'cvx1000'
}

g_cfg_data = {
    'default': {
        'regex_match': '3\.1\.[12]',
        'image': 'CumulusLinux-3.1.2-amd64.bin'
    },
    'group_a': {
        'regex_match': '3\.1\.[12]',
        'image': 'CumulusLinux-3.1.2-amd64.bin',
        'matches': {
            'hw_model': ['cvx1000'],
            'mac_address': ['0123456789012', '2109876543210']
        }
    }
}


def os_sel_file(contents=None):
    """
    Used to create a temporary os-selector file
    :param contents: python dictionary that will be converted to yaml
    :return: returns a temporary file string
    """
    if not contents:
        contents = g_cfg_data
    os_sel = tempfile.NamedTemporaryFile(mode='w+t')
    os_sel.file.write(yaml.dump(contents, default_flow_style=False))
    os_sel.file.flush()
    return os_sel


def test_cli_parse():
    osf = os_sel_file()
    parse = aztp_os_selector.cli_parse(['-j', '{"test_key": "test_value"}', '-c', str(osf)])
    assert json.loads(parse.json)['test_key'] == 'test_value'
    assert parse.config_file == str(osf)


def test_cli_parse_parsererror():
    osf = os_sel_file()
    with pytest.raises(aztp_os_selector.ArgumentParser.ParserError) as e:
        aztp_os_selector.cli_parse(['-c', osf.name])
    assert 'ParserError' in str(e)


def test_exit_results():
    results = json.loads('{"ok": "True"}')
    # Supress stdout from exit_results
    old_stdout = sys.stdout
    sys.stdout = open(os.devnull, "w")
    try:
        aztp_os_selector.exit_results(results)
    except SystemExit as e:
        pass
    finally:
        # resume stdout
        sys.stdout.close()
        sys.stdout = old_stdout

    assert str(e) == '0'


def test_load_cfg():
    contents = {'default': {
        'regex_match': '3\.1\.[12]',
        'image': 'CumulusLinux-3.1.2-amd64.bin'}}
    osf = os_sel_file(contents=contents)
    cfg = aztp_os_selector.load_cfg(osf.name)
    assert cfg == contents


def test_load_nonexistent_cfg():
    # Supress stdout from exit_results
    old_stdout = sys.stdout
    sys.stdout = open(os.devnull, "w")
    try:
        aztp_os_selector.load_cfg('filename_that_does_not_exist')
    except SystemExit as e:
        pass
    finally:
        # resume stdout
        sys.stdout.close()
        sys.stdout = old_stdout
    assert str(e) == '1'


def test_load_cfg_bad_syntax():
    bad_yaml = '%%%%%%%%'
    os_sel = tempfile.NamedTemporaryFile(mode='w+b')
    os_sel.file.write(bad_yaml)
    os_sel.file.flush()

    # Supress stdout from exit_results
    old_stdout = sys.stdout
    sys.stdout = open(os.devnull, "w")
    try:
        aztp_os_selector.load_cfg(os_sel.name)
    except SystemExit as e:
        pass
    finally:
        # resume stdout
        sys.stdout.close()
        sys.stdout = old_stdout
    assert str(e) == '1'


def test_match_hw_model():
    match = aztp_os_selector.match_hw_model(g_dev_data, g_cfg_data)
    assert match[0] == 'group_a'
    assert match[1] == g_cfg_data['group_a']


def test_match_hw_model_no_match():
    new_dev_data = copy.deepcopy(g_dev_data)
    new_dev_data['hw_model'] = 'cvx2000'
    match = aztp_os_selector.match_hw_model(new_dev_data, g_cfg_data)
    assert match[0] == 'default'
    assert match[1] == g_cfg_data['default']


def test_match_hw_model_no_default():
    new_dev_data = copy.deepcopy(g_dev_data)
    new_dev_data['hw_model'] = 'cvx2000'
    new_cfg_data = copy.deepcopy(g_cfg_data)
    new_cfg_data.pop('default')
    try:
        aztp_os_selector.match_hw_model(new_dev_data, new_cfg_data)
    except aztp_os_selector.HwNoMatchError as e:
        pass
    assert isinstance(e, aztp_os_selector.HwNoMatchError)


def test_match_hw_model_multi_match():
    new_cfg_data = copy.deepcopy(g_cfg_data)
    new_cfg_data['group_b'] = {
        'regex_match': '3\.1\.[12]',
        'image': 'CumulusLinux-3.1.2-amd64.bin',
        'matches': {
            'hw_model': ['cvx1000'],
            'mac_address': ['0123456789012', '2109876543210']
        }
    }
    try:
        aztp_os_selector.match_hw_model(g_dev_data, new_cfg_data)
    except aztp_os_selector.HwMultiMatchError as e:
        pass
    assert isinstance(e, aztp_os_selector.HwMultiMatchError)


def test_match_os_version_regex_no_upgrade():
    item_match = namedtuple('item_match', ['hw_match', 'data'])
    hw_match = item_match('group_a', g_cfg_data['group_a'])
    upgrade = aztp_os_selector.match_os_version(g_dev_data, hw_match.data)
    assert not upgrade


def test_match_os_version_exact_match_no_upgrade():
    new_cfg_data = copy.deepcopy(g_cfg_data)
    new_cfg_data['group_a'].pop('regex_match')
    new_cfg_data['group_a']['exact_match'] = '3.1.1'
    item_match = namedtuple('item_match', ['hw_match', 'data'])
    hw_match = item_match('group_a', new_cfg_data['group_a'])
    upgrade = aztp_os_selector.match_os_version(g_dev_data, hw_match.data)
    assert not upgrade


def test_match_os_version_regex_upgrade():
    new_cfg_data = copy.deepcopy(g_cfg_data)
    new_cfg_data['group_a']['regex_match'] = '3\.1\.[23]'
    item_match = namedtuple('item_match', ['hw_match', 'data'])
    hw_match = item_match('group_a', new_cfg_data['group_a'])
    upgrade = aztp_os_selector.match_os_version(g_dev_data, hw_match.data)
    assert upgrade == new_cfg_data['group_a']['image']


def test_match_os_version_exact_match_upgrade():
    new_cfg_data = copy.deepcopy(g_cfg_data)
    new_cfg_data['group_a'].pop('regex_match')
    new_cfg_data['group_a']['exact_match'] = '3.1.0'
    item_match = namedtuple('item_match', ['hw_match', 'data'])
    hw_match = item_match('group_a', new_cfg_data['group_a'])
    upgrade = aztp_os_selector.match_os_version(g_dev_data, hw_match.data)
    assert upgrade == new_cfg_data['group_a']['image']
