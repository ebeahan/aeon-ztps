import pytest
from mock import call, patch, Mock, MagicMock
import os
from copy import deepcopy
from tempfile import NamedTemporaryFile
from shutil import copyfile
import hashlib
import json

from aeon_ztp.bin import eos_bootstrap
from aeon.eos.device import Device
from aeon.exceptions import ConfigError, CommandError, ProbeError, UnauthorizedError

args = {
    'target': '1.1.1.1',
    'server': '2.2.2.2',
    'topdir': '/tmp/dir',
    'logfile': '/tmp/logfile',
    'reload_delay': '60',
    'init_delay': '90',
    'user': 'admin',
    'env_user': 'ENV_USER',
    'env_passwd': 'ENV_PASS'
}

# Facts for device that will not be upgraded
factsv416 = {
    'hw_version': '02.11',
    'hw_part_number': None,
    'hostname': 'localhost',
    'fqdn': 'localhost.com',
    'chassis_id': None,
    'vendor': 'arista',
    'os_version': '4.16.6M',
    'virtual': False,
    'hw_model': 'DCS-7050QX-32-F',
    'serial_number': 'JPE11111111',
    'hw_part_version': None,
    'os': 'eos'
}

factsv416['facts'] = json.dumps(factsv416)

# Device that will be upgraded
facts_v410 = dict(factsv416)
facts_v410['os_version'] = '4.10.1'

# vEOS Device
facts_veos = dict(factsv416)
facts_veos['virtual'] = True


@pytest.fixture()
def cli_args():

    parse = eos_bootstrap.cli_parse(['--target', args['target'],
                                     '--server', args['server'],
                                     '--topdir', args['topdir'],
                                     '--logfile', args['logfile'],
                                     '--reload-delay', args['reload_delay'],
                                     '--init-delay', args['init_delay'],
                                     '--user', args['user'],
                                     '--env-user', args['env_user'],
                                     '--env-passwd', args['env_passwd']])
    return parse


# Prevent all requests calls
@pytest.fixture(autouse=True)
def no_requests(monkeypatch):
    mock_response = MagicMock()
    monkeypatch.setattr('requests.sessions.Session.request', mock_response)


@patch('aeon.eos.device.Connector')
# Parametrize device to test Cumulus v2, v3.1.1, v3.1.2, and VX
@pytest.fixture(params=[facts_v410, factsv416, facts_veos], ids=['EOSv410', 'EOSv416', 'vEOS'])
def device(mock_con, request):
    dev = Device(args['target'], no_probe=True, no_gather_facts=True)
    dev.facts = request.param
    print dev
    return dev


@pytest.fixture()
def eb_obj(cli_args):
    os.environ['ENV_PASS'] = 'admin'
    eb = eos_bootstrap.EosBootstrap(args['server'], cli_args)
    return eb


def test_cli_parse(cli_args):
    for arg in vars(cli_args):
        assert str(getattr(cli_args, arg)) == args[arg]


def test_eos_bootstrap(cli_args, eb_obj):
    assert args['server'] == eb_obj.server
    assert cli_args == eb_obj.cli_args


@patch('aeon_ztp.bin.eos_bootstrap.requests')
def test_post_device_facts(mock_requests, device, eb_obj):
    eb_obj.dev = device
    eb_obj.post_device_facts()
    mock_requests.put.assert_called_with(json={
        'os_version': device.facts['os_version'],
        'os_name': device.facts['os'],
        'ip_addr': device.target,
        'hw_model': device.facts['hw_model'],
        'serial_number': device.facts['serial_number'],
        'facts': json.dumps(device.facts),
        'image_name': None,
        'finally_script': None
    },
        url='http://{}/api/devices/facts'.format(args['server']))


@patch('aeon_ztp.bin.eos_bootstrap.requests')
def test_post_device_status(mock_requests, device, eb_obj):
    kw = {
        'message': 'Test message',
        'state': 'DONE'
    }
    eb_obj.dev = device
    eb_obj.post_device_status(**kw)
    mock_requests.put.assert_called_with(json={
        'message': kw['message'],
        'os_name': device.facts['os'],
        'ip_addr': device.target,
        'state': kw['state']
    },
        url='http://{}/api/devices/status'.format(args['server']))


def test_post_device_status_no_dev(eb_obj):
    eb_obj.log = MagicMock()
    message = 'test message'
    eb_obj.target = None
    eb_obj.post_device_status(message=message)
    eb_obj.log.error.assert_called_with('Either dev or target is required to post device status. Message was: {}'.format(message))


@patch('aeon_ztp.bin.eos_bootstrap.EosBootstrap.post_device_status')
def test_exit_results(mock_post, eb_obj, device):
    kw = {
        'results': {'ok': True},
        'exit_error': None,
    }
    with pytest.raises(SystemExit) as e:
        eb_obj.exit_results(**kw)
    mock_post.assert_called_with(
        state='DONE',
        message='bootstrap completed OK'
    )
    assert e.value.code == 0

    # Test bad exit
    kw = {
        'results': {'ok': False,
                    'message': 'Error Message'},
        'exit_error': 1,
    }
    with pytest.raises(SystemExit) as e:
        eb_obj.exit_results(**kw)
    mock_post.assert_called_with(
        state='FAILED',
        message=kw['results']['message']
    )
    assert e.value.code == 1


@patch('aeon_ztp.bin.eos_bootstrap.EosBootstrap.exit_results', side_effect=SystemExit)
def test_wait_for_device_missing_username(mock_exit, cli_args, device):
    new_args = deepcopy(cli_args)
    new_args.user = None
    new_args.env_user = None
    with pytest.raises(SystemExit):
        eos_bootstrap.EosBootstrap(args['server'], new_args)
    mock_exit.assert_called_with(
        results={'ok': False,
                 'error_type': 'login',
                 'message': 'login user-name missing'}
    )


@patch('aeon_ztp.bin.eos_bootstrap.EosBootstrap.exit_results', side_effect=SystemExit)
def test_wait_for_device_missing_passwd(mock_exit, cli_args, device):
    new_args = deepcopy(cli_args)
    new_args.env_passwd = None
    with pytest.raises(SystemExit):
        eos_bootstrap.EosBootstrap(args['server'], new_args)
    mock_exit.assert_called_with(
        results={'ok': False,
                 'error_type': 'login',
                 'message': 'login user-password missing'}
    )


@patch('aeon_ztp.bin.eos_bootstrap.time')
@patch('aeon_ztp.bin.eos_bootstrap.EosBootstrap.exit_results', side_effect=SystemExit)
@patch('aeon_ztp.bin.eos_bootstrap.Device')
@patch('aeon_ztp.bin.eos_bootstrap.EosBootstrap.post_device_status')
def test_wait_for_device_command_error(mock_post_dev, mock_dev, mock_exit, mock_time, eb_obj):
    mock_dev.side_effect = CommandError(Exception, 'test error')
    with pytest.raises(SystemExit):
        eb_obj.wait_for_device(2, 1)
    errmsg = 'Failed to access %s device API within reload countdown' % eb_obj.cli_args.target
    mock_exit.assert_called_with(
        exit_error=errmsg,
        results={'ok': False,
                 'error_type': 'login',
                 'message': errmsg
                 }
    )


@patch('aeon_ztp.bin.eos_bootstrap.EosBootstrap.exit_results', side_effect=SystemExit)
@patch('aeon_ztp.bin.eos_bootstrap.Device', side_effect=ProbeError)
@patch('aeon_ztp.bin.eos_bootstrap.EosBootstrap.post_device_status')
def test_wait_for_device_probe_error(mock_post_dev, mock_dev, mock_exit, eb_obj):
    with pytest.raises(SystemExit):
        eb_obj.wait_for_device(1, 2)
    errmsg = 'Failed to probe target %s within reload countdown' % eb_obj.cli_args.target
    mock_exit.assert_called_with(
        exit_error=errmsg,
        results={'ok': False,
                 'error_type': 'login',
                 'message': errmsg
                 }
    )


@patch('aeon_ztp.bin.eos_bootstrap.EosBootstrap.exit_results', side_effect=SystemExit)
@patch('aeon_ztp.bin.eos_bootstrap.Device', side_effect=UnauthorizedError)
@patch('aeon_ztp.bin.eos_bootstrap.EosBootstrap.post_device_status')
def test_wait_for_device_unauthorized_error(mock_post_dev, mock_dev, mock_exit, eb_obj):
    with pytest.raises(SystemExit):
        eb_obj.wait_for_device(1, 2)
    errmsg = 'Unauthorized - check user/password'
    mock_exit.assert_called_with(
        exit_error=errmsg,
        results={'ok': False,
                 'error_type': 'login',
                 'message': errmsg
                 }
    )


@patch('aeon_ztp.bin.eos_bootstrap.Device')
@patch('aeon_ztp.bin.eos_bootstrap.EosBootstrap.post_device_facts')
def test_wait_for_device(mock_post_facts, mock_dev, eb_obj):
    poll_delay = 2
    eb_obj.wait_for_device(1, poll_delay)
    mock_dev.assert_called_with(
        eb_obj.cli_args.target,
        passwd=os.environ['ENV_PASS'],
        timeout=poll_delay,
        user=eb_obj.cli_args.user or os.getenv(eb_obj.cli_args.env_user)
    )
    mock_post_facts.assert_called()


def test_do_push_config_no_conf_file(device, eb_obj):
    eb_obj.dev = device
    eb_obj.do_push_config()
    assert not device.api.execute.called


@patch('aeon_ztp.bin.eos_bootstrap.open')
@patch('aeon_ztp.bin.eos_bootstrap.os.path.isfile', return_value=True)
@patch('aeon_ztp.bin.eos_bootstrap.EosBootstrap.exit_results', side_effect=SystemExit)
def test_do_push_config_configerror(mock_exit, mock_isfile, mock_open, device, eb_obj):
    eb_obj.dev = device
    all_config = 'transceiver qsfp default-mode 4x10G'
    errmsg = 'test config error'
    device.api.configure.side_effect = ConfigError(Exception(errmsg), all_config)
    with pytest.raises(SystemExit):
        eb_obj.do_push_config()
    mock_exit.assert_called_with(
        {
            'ok': False,
            'error_type': 'config',
            'message': errmsg
        }
    )


@patch('aeon_ztp.bin.eos_bootstrap.open')
@patch('aeon_ztp.bin.eos_bootstrap.os.path.isfile', return_value=True)
def test_do_push_config(mock_isfile, mock_open, device, eb_obj):
    eb_obj.dev = device
    all_config = 'transceiver qsfp default-mode 4x10G\nmore config'
    model_config = 'model config\nmore model config'
    mock_open.return_value.read.return_value.split.side_effect = [all_config.split('\n'), model_config.split('\n')]
    eb_obj.do_push_config()
    device.api.configure.assert_has_calls([call(all_config.split('\n')), call(model_config.split('\n'))], any_order=False)
    device.api.execute.assert_called_with(['enable', 'copy running-config startup-config'])


def test_ensure_md5sum_md5_exists(eb_obj):
    test_file = NamedTemporaryFile()
    test_md5_file = test_file.name + '.md5'
    copyfile(test_file.name, test_md5_file)
    with open(test_file.name, 'rb') as f:
        expected_md5sum = hashlib.md5(f.read()).hexdigest()
    with open(test_md5_file, 'a') as f:
        f.write(expected_md5sum)
    actual_md5sum = eb_obj.ensure_md5sum(test_file.name)
    assert expected_md5sum == actual_md5sum


def test_ensure_md5sum_md5_doesnt_exist(eb_obj):
    test_file = NamedTemporaryFile()
    with open(test_file.name, 'rb') as f:
        expected_md5sum = hashlib.md5(f.read()).hexdigest()
    actual_md5sum = eb_obj.ensure_md5sum(test_file.name)
    assert expected_md5sum == actual_md5sum


@patch('aeon_ztp.bin.eos_bootstrap.EosBootstrap.exit_results', side_effect=SystemExit)
@patch('aeon_ztp.bin.eos_bootstrap.json.loads')
@patch('aeon_ztp.bin.eos_bootstrap.subprocess.Popen')
def test_check_os_install_json_exception(mock_subprocess, mock_json, mock_exit, eb_obj, device):
    eb_obj.dev = device
    test_stdout = 'test stdout'
    exception_msg = 'test exception message'
    errmsg = 'Unable to load os-select output as JSON: {}\n {}'.format(test_stdout, exception_msg)
    mock_json.side_effect = Exception(exception_msg)
    mock_subprocess.return_value.communicate.return_value = (test_stdout, 'test stderr')
    with pytest.raises(SystemExit):
        eb_obj.check_os_install_and_finally()
    mock_exit.assert_called_with(
        exit_error=errmsg,
        results={
            'ok': False,
            'error_type': 'install',
            'message': errmsg
        }
    )


@patch('aeon_ztp.bin.eos_bootstrap.EosBootstrap.exit_results', side_effect=SystemExit)
@patch('aeon_ztp.bin.eos_bootstrap.subprocess.Popen')
def test_check_os_install(mock_subprocess, mock_exit, eb_obj, device):
    eb_obj.dev = device
    aztp_file = '{}/bin/aztp_os_selector.py'.format(eb_obj.cli_args.topdir)
    conf_fpath = '{}/etc/profiles/eos/os-selector.cfg'.format(eb_obj.cli_args.topdir)
    facts = json.dumps(device.facts)
    json_string = '{"test_key": "test_value"}'
    mock_subprocess.return_value.communicate.return_value = (json_string, 'test stderr')
    results = eb_obj.check_os_install_and_finally()
    mock_subprocess.assert_called_with('{aztp_file} -j \'{facts}\' -c {conf_fpath}'.format(aztp_file=aztp_file,
                                                                                           facts=facts,
                                                                                           conf_fpath=conf_fpath),
                                       shell=True, stdout=-1)
    assert results == json.loads(json_string)


@patch('aeon_ztp.bin.eos_bootstrap.EosBootstrap.exit_results', side_effect=SystemExit)
@patch('aeon_ztp.bin.eos_bootstrap.os.path.isfile', return_value=False)
def test_do_os_install_missing_image(mock_isfile, mock_exit, eb_obj, device):
    image_name = 'test_image'
    eb_obj.dev = device
    eb_obj.image_name = image_name
    image_fpath = os.path.join(eb_obj.cli_args.topdir, 'vendor_images', device.facts['os'], image_name)
    errmsg = 'image file {} does not exist'.format(image_fpath)
    with pytest.raises(SystemExit):
        eb_obj.do_os_install()
    mock_exit.assert_called_with(
        results={
            'ok': False,
            'error_type': 'install',
            'message': errmsg
        }
    )


@patch('aeon_ztp.bin.eos_bootstrap.EosBootstrap.exit_results', side_effect=SystemExit)
@patch('aeon_ztp.bin.eos_bootstrap.os.path.isfile', return_value=True)
def test_do_os_install_command_error(mock_isfile, mock_exit, eb_obj, device):
    eb_obj.ensure_md5sum = MagicMock
    device.api.execute.side_effect = [CommandError(Exception('some exception'), 'commands'), Exception('bad command')]
    image_name = 'test_image'
    eb_obj.dev = device
    eb_obj.image_name = image_name
    errmsg = "Unable to copy file to device: %s" % str('bad command')
    with pytest.raises(SystemExit):
        eb_obj.do_os_install()
    mock_exit.assert_called_with(
        results={
            'ok': False,
            'error_type': 'install',
            'message': errmsg
        }
    )


@patch('aeon_ztp.bin.eos_bootstrap.EosBootstrap.exit_results', side_effect=SystemExit)
@patch('aeon_ztp.bin.eos_bootstrap.os.path.isfile', return_value=True)
def test_do_os_install(mock_isfile, mock_exit, eb_obj, device):
    image_name = 'EOS-4.16.6M.swi'
    image_md5 = '0899eaad7f62e995a5fd109839f926eb'
    eb_obj.dev = device
    eb_obj.image_name = image_name
    eb_obj.ensure_md5sum = Mock(return_value=image_md5)
    # First return is for cmd execute, second retval is results of md5 command
    device.api.execute.side_effect = ['',
                                      {'messages': ['verify /md5 (flash:{image_name}) = {image_md5}'.format(
                                          image_name=image_name, image_md5=image_md5)]},
                                      '']

    eb_obj.do_os_install()
    exe_expected_calls = [call('dir flash:{}'.format(image_name)),
                          call('verify /md5 flash:{}'.format(image_name)),
                          call('copy running-config startup-config')]
    conf_expected_calls = [call(['boot system flash:{}'.format(image_name)])]
    device.api.execute.assert_has_calls(exe_expected_calls)
    device.api.configure.assert_has_calls(conf_expected_calls)


@patch('aeon_ztp.bin.eos_bootstrap.EosBootstrap.exit_results', side_effect=SystemExit)
@patch('aeon_ztp.bin.eos_bootstrap.os.path.isfile', return_value=True)
def test_do_os_install_md5_mismatch(mock_isfile, mock_exit, eb_obj, device):
    image_name = 'EOS-4.16.6M.swi'
    image_md5 = '0899eaad7f62e995a5fd109839f926eb'
    bad_image_md5 = 'foooooooo'
    eb_obj.dev = device
    eb_obj.image_name = image_name
    eb_obj.ensure_md5sum = Mock(return_value=image_md5)
    # First return is for cmd execute, second retval is results of md5 command
    device.api.execute.side_effect = ['', {'messages': ['verify /md5 (flash:{image_name}) = {image_md5}'.format(
                                      image_name=image_name, image_md5=bad_image_md5)]}]
    with pytest.raises(SystemExit):
        eb_obj.do_os_install()

    mock_exit.assert_called_with(
        results={
            'ok': False,
            'error_type': 'install',
            'message': 'image file {filename} MD5 mismatch has={has} should={should}'
            .format(filename=image_name, has=bad_image_md5, should=image_md5)
        }
    )


def test_do_ensure_os_version_no_install(eb_obj, device):
    eb_obj.check_os_install_and_finally = Mock(return_value={'image': None})
    eb_obj.dev = device
    retval = eb_obj.do_ensure_os_version()
    assert retval == device


@patch('aeon_ztp.bin.eos_bootstrap.time')
def test_do_ensure_os_version(mock_time, eb_obj, device):
    image_name = 'EOS-4.16.6M.swi'
    finally_script = 'finally'
    eb_obj.dev = device
    eb_obj.image_name = image_name
    eb_obj.finally_script = finally_script
    eb_obj.check_os_install_and_finally = Mock(return_value={'image': image_name, 'finally': finally_script})
    eb_obj.do_os_install = MagicMock()
    eb_obj.wait_for_device = Mock(return_value=device)
    retval = eb_obj.do_ensure_os_version()

    eb_obj.do_os_install.assert_called()
    device.api.execute.assert_called_with('reload now')
    assert retval == device


@patch('aeon_ztp.bin.eos_bootstrap.EosBootstrap')
@patch('aeon_ztp.bin.eos_bootstrap.EosBootstrap.check_os_install_and_finally')
@patch('aeon_ztp.bin.eos_bootstrap.EosBootstrap.do_ensure_os_version')
@patch('aeon_ztp.bin.eos_bootstrap.EosBootstrap.wait_for_device')
@patch('aeon_ztp.bin.eos_bootstrap.EosBootstrap.exit_results', side_effect=SystemExit)
@patch('aeon_ztp.bin.eos_bootstrap.os.path.isdir', return_value=True)
@patch('aeon_ztp.bin.eos_bootstrap.time')
@patch('aeon_ztp.bin.eos_bootstrap.cli_parse')
def test_main(mock_cli_parse, mock_time, mock_isdir, mock_exit, mock_wait, mock_ensure_os, mock_check_os_and_finally, mock_eb, cli_args, device, eb_obj):
    mock_cli_parse.return_value = cli_args
    mock_wait.return_value = device
    eb_obj.dev = device
    mock_eb.return_value = eb_obj
    with pytest.raises(SystemExit):
        eos_bootstrap.main()
    mock_exit.assert_called_with({'ok': True})
    mock_wait.assert_called_with(countdown=cli_args.reload_delay, poll_delay=10)
    if device.facts['virtual']:
        assert not mock_ensure_os.called
    else:
        mock_ensure_os.assert_called()


@patch('aeon_ztp.bin.eos_bootstrap.EosBootstrap.exit_results', side_effect=SystemExit)
@patch('aeon_ztp.bin.eos_bootstrap.os.path.isdir', return_value=False)
@patch('aeon_ztp.bin.eos_bootstrap.cli_parse')
def test_main_no_topdir(mock_cli_parse, mock_is_dir, mock_exit, cli_args):
    mock_cli_parse.return_value = cli_args
    exc = '{} is not a directory'.format(cli_args.topdir)
    with pytest.raises(SystemExit):
        eos_bootstrap.main()
    mock_exit.assert_called_with({'ok': False,
                                  'error_type': 'args',
                                  'message': exc})
