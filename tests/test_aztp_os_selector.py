import os
import yaml
import tempfile
import json
import sys
import copy
from collections import namedtuple
import pytest
from mock import patch

from aeon_ztp.bin import aztp_os_selector


dev_data = {
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

cfg_data = {
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


@pytest.fixture()
def cli_args():

    parse = aztp_os_selector.cli_parse(['--json', json.dumps(dev_data),
                                        '--config', 'os-selector.cfg'])
    return parse


def os_sel_file(contents=None):
    """
    Used to create a temporary os-selector file
    :param contents: python dictionary that will be converted to yaml
    :return: returns a temporary file string
    """
    if not contents:
        contents = cfg_data
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
    match = aztp_os_selector.match_hw_model(dev_data, cfg_data)
    assert match[0] == 'group_a'
    assert match[1] == cfg_data['group_a']


def test_match_hw_model_no_match():
    new_dev_data = copy.deepcopy(dev_data)
    new_dev_data['hw_model'] = 'cvx2000'
    match = aztp_os_selector.match_hw_model(new_dev_data, cfg_data)
    assert match[0] == 'default'
    assert match[1] == cfg_data['default']


def test_match_hw_model_no_default():
    new_dev_data = copy.deepcopy(dev_data)
    new_dev_data['hw_model'] = 'cvx2000'
    new_cfg_data = copy.deepcopy(cfg_data)
    new_cfg_data.pop('default')
    try:
        aztp_os_selector.match_hw_model(new_dev_data, new_cfg_data)
    except aztp_os_selector.HwNoMatchError as e:
        pass
    assert isinstance(e, aztp_os_selector.HwNoMatchError)


def test_match_hw_model_multi_match():
    new_cfg_data = copy.deepcopy(cfg_data)
    new_cfg_data['group_b'] = {
        'regex_match': '3\.1\.[12]',
        'image': 'CumulusLinux-3.1.2-amd64.bin',
        'matches': {
            'hw_model': ['cvx1000'],
            'mac_address': ['0123456789012', '2109876543210']
        }
    }
    try:
        aztp_os_selector.match_hw_model(dev_data, new_cfg_data)
    except aztp_os_selector.HwMultiMatchError as e:
        pass
    assert isinstance(e, aztp_os_selector.HwMultiMatchError)


def test_match_os_version_regex_no_upgrade():
    item_match = namedtuple('item_match', ['hw_match', 'data'])
    hw_match = item_match('group_a', cfg_data['group_a'])
    upgrade = aztp_os_selector.match_os_version(dev_data, hw_match.data)
    assert not upgrade


def test_match_os_version_exact_match_no_upgrade():
    new_cfg_data = copy.deepcopy(cfg_data)
    new_cfg_data['group_a'].pop('regex_match')
    new_cfg_data['group_a']['exact_match'] = '3.1.1'
    item_match = namedtuple('item_match', ['hw_match', 'data'])
    hw_match = item_match('group_a', new_cfg_data['group_a'])
    upgrade = aztp_os_selector.match_os_version(dev_data, hw_match.data)
    assert not upgrade


def test_match_os_version_regex_upgrade():
    new_cfg_data = copy.deepcopy(cfg_data)
    new_cfg_data['group_a']['regex_match'] = '3\.1\.[23]'
    item_match = namedtuple('item_match', ['hw_match', 'data'])
    hw_match = item_match('group_a', new_cfg_data['group_a'])
    upgrade = aztp_os_selector.match_os_version(dev_data, hw_match.data)
    assert upgrade == new_cfg_data['group_a']['image']


def test_match_os_version_exact_match_upgrade():
    new_cfg_data = copy.deepcopy(cfg_data)
    new_cfg_data['group_a'].pop('regex_match')
    new_cfg_data['group_a']['exact_match'] = '3.1.0'
    item_match = namedtuple('item_match', ['hw_match', 'data'])
    hw_match = item_match('group_a', new_cfg_data['group_a'])
    upgrade = aztp_os_selector.match_os_version(dev_data, hw_match.data)
    assert upgrade == new_cfg_data['group_a']['image']


def test_match_os_version_cfgerror():
    with pytest.raises(aztp_os_selector.CfgError):
        dev_data = {'os_version': '1.A'}
        hw_match = []
        aztp_os_selector.match_os_version(dev_data, hw_match)


@patch('aeon_ztp.bin.aztp_os_selector.exit_results', side_effect=SystemExit)
@patch('aeon_ztp.bin.aztp_os_selector.json.loads')
@patch('aeon_ztp.bin.aztp_os_selector.load_cfg', return_value=cfg_data)
@patch('aeon_ztp.bin.aztp_os_selector.cli_parse')
def test_main_json_error(mock_cli_parse, mock_load_cfg, mock_json_load, mock_exit_results, cli_args):
    mock_json_load.side_effect = ValueError()
    mock_cli_parse.return_value = cli_args
    with pytest.raises(SystemExit):
        aztp_os_selector.main()
    mock_exit_results.assert_called_with({'ok': False,
                                          'error_type': 'args',
                                          'error_message': 'JSON argument formatted incorrectly.'})


@patch('aeon_ztp.bin.aztp_os_selector.exit_results', side_effect=SystemExit)
@patch('aeon_ztp.bin.aztp_os_selector.cli_parse')
def test_main_argparse_error(mock_cli_parse, mock_exit_results, cli_args):
    errmsg = 'test parse error'
    mock_cli_parse.side_effect = aztp_os_selector.ArgumentParser.ParserError(errmsg)
    with pytest.raises(SystemExit):
        aztp_os_selector.main()
    mock_exit_results.assert_called_with({'ok': False,
                                          'error_type': 'args',
                                          'error_message': errmsg})


@patch('aeon_ztp.bin.aztp_os_selector.match_hw_model', side_effect=aztp_os_selector.HwNoMatchError)
@patch('aeon_ztp.bin.aztp_os_selector.exit_results', side_effect=SystemExit)
@patch('aeon_ztp.bin.aztp_os_selector.json.loads')
@patch('aeon_ztp.bin.aztp_os_selector.load_cfg', return_value=cfg_data)
@patch('aeon_ztp.bin.aztp_os_selector.cli_parse')
def test_main_hwnomatch_error(mock_cli_parse, mock_load_cfg, mock_json_load, mock_exit_results, mock_hw_match, cli_args):
    errmsg = 'no matching hw_model value'
    mock_cli_parse.return_value = cli_args
    with pytest.raises(SystemExit):
        aztp_os_selector.main()
    mock_exit_results.assert_called_with({'ok': False,
                                          'error_type': 'hw_match',
                                          'error_message': errmsg})


@patch('aeon_ztp.bin.aztp_os_selector.match_hw_model', side_effect=aztp_os_selector.HwMultiMatchError)
@patch('aeon_ztp.bin.aztp_os_selector.exit_results', side_effect=SystemExit)
@patch('aeon_ztp.bin.aztp_os_selector.json.loads')
@patch('aeon_ztp.bin.aztp_os_selector.load_cfg', return_value=cfg_data)
@patch('aeon_ztp.bin.aztp_os_selector.cli_parse')
def test_main_hwmultimatch_error(mock_cli_parse, mock_load_cfg, mock_json_load, mock_exit_results, mock_hw_match, cli_args):
    errmsg = 'matches multiple os-selector groups'
    mock_hw_match.side_effect = aztp_os_selector.HwMultiMatchError(errmsg)
    mock_cli_parse.return_value = cli_args
    with pytest.raises(SystemExit):
        aztp_os_selector.main()
    mock_exit_results.assert_called_with({'ok': False,
                                          'error_type': 'hw_match',
                                          'error_message': errmsg})


@patch('aeon_ztp.bin.aztp_os_selector.match_os_version')
@patch('aeon_ztp.bin.aztp_os_selector.match_hw_model')
@patch('aeon_ztp.bin.aztp_os_selector.exit_results', side_effect=SystemExit)
@patch('aeon_ztp.bin.aztp_os_selector.json.loads')
@patch('aeon_ztp.bin.aztp_os_selector.load_cfg', return_value=cfg_data)
@patch('aeon_ztp.bin.aztp_os_selector.cli_parse')
def test_main_cfgerror(mock_cli_parse, mock_load_cfg, mock_json_load, mock_exit_results, mock_hw_match,
                       mock_os_match, cli_args):
    errmsg = 'Expecting one of'
    mock_os_match.side_effect = aztp_os_selector.CfgError(errmsg)
    mock_cli_parse.return_value = cli_args
    with pytest.raises(SystemExit):
        aztp_os_selector.main()
    mock_exit_results.assert_called_with({'ok': False,
                                          'error_type': 'cfg_error',
                                          'error_message': errmsg})


@patch('aeon_ztp.bin.aztp_os_selector.match_os_version')
@patch('aeon_ztp.bin.aztp_os_selector.match_hw_model')
@patch('aeon_ztp.bin.aztp_os_selector.exit_results', side_effect=SystemExit)
@patch('aeon_ztp.bin.aztp_os_selector.json.loads')
@patch('aeon_ztp.bin.aztp_os_selector.load_cfg', return_value=cfg_data)
@patch('aeon_ztp.bin.aztp_os_selector.cli_parse')
def test_main(mock_cli_parse, mock_load_cfg, mock_json_load, mock_exit_results, mock_hw_match,
              mock_os_match, cli_args):
    sw_match = '1.0.0'
    item_match = namedtuple('item_match', ['hw_match', 'data'])
    hw_match = item_match(hw_match='default', data={'image': '1.0.1b',
                                                    'exact_match': '4.16.6M',
                                                    'finally': 'finally'})
    mock_hw_match.return_value = hw_match
    mock_os_match.return_value = sw_match
    mock_cli_parse.return_value = cli_args
    with pytest.raises(SystemExit):
        aztp_os_selector.main()
    mock_exit_results.assert_called_with({'ok': True, 'image_name': sw_match, 'finally': hw_match.data['finally']})
