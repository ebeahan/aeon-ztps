from mock import Mock, MagicMock, patch, call
from copy import deepcopy
import os
import pytest
import json
from tempfile import NamedTemporaryFile
from shutil import copyfile
import hashlib

from aeon_ztp.bin import nxos_bootstrap
from aeon.nxos.device import Device
import aeon.nxos.exceptions as NxExc
from aeon.exceptions import ProbeError, UnauthorizedError


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

factsv703 = {
    'vendor': 'cisco',
    'hw_part_number': '73-16523-04',
    'hostname': 'switch',
    'fqdn': 'switch',
    'chassis_id': 'Nexus9000 C9372PX chassis',
    'domain_name': '',
    'os_version': '7.0(3)I2(2d)',
    'hw_version': '2.0',
    'virtual': False,
    'hw_model': 'N9K-C9372PX',
    'serial_number': 'SAL1919ABCD',
    'hw_part_version': 'A0',
    'os': 'nxos'
}

factsv703['facts'] = json.dumps(factsv703)

factsv700 = dict(factsv703)
factsv700['os_version'] = '7.0(0)I2(2d)'

facts_nxosv = dict(factsv700)
facts_nxosv['virtual'] = True


@pytest.fixture()
def cli_args():

    parse = nxos_bootstrap.cli_parse(['--target', args['target'],
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


@patch('aeon.nxos.device.Connector')
# Parametrize device to test NXOS 7.0(3), 7.0(0), and NXOSv
@pytest.fixture(params=[factsv703, factsv700, facts_nxosv], ids=['NXOS_703', 'NXOS_700', 'NXOSv'])
def device(mock_con, request):
    dev = Device(args['target'], no_probe=True, no_gather_facts=True)
    dev.facts = request.param
    return dev


@pytest.fixture()
def nb_obj(cli_args):
    os.environ['ENV_PASS'] = 'admin'
    nb = nxos_bootstrap.NxosBootstrap(args['server'], cli_args)
    return nb


def test_cli_parse(cli_args):
    for arg in vars(cli_args):
        assert str(getattr(cli_args, arg)) == args[arg]


def test_nxos_bootstrap(cli_args, nb_obj):
    assert args['server'] == nb_obj.server
    assert cli_args == nb_obj.cli_args


@patch('aeon_ztp.bin.nxos_bootstrap.requests')
def test_post_device_facts(mock_requests, device, nb_obj):
    nb_obj.dev = device
    nb_obj.post_device_facts()
    mock_requests.put.assert_called_with(json={
        'os_version': device.facts['os_version'],
        'os_name': nb_obj.os_name,
        'ip_addr': device.target,
        'hw_model': device.facts['hw_model'],
        'serial_number': device.facts['serial_number'],
        'facts': json.dumps(device.facts),
        'image_name': None,
        'finally_script': None
    },
        url='http://{}/api/devices/facts'.format(args['server']))


@patch('aeon_ztp.bin.nxos_bootstrap.requests')
def test_post_device_status(mock_requests, device, nb_obj):
    kw = {
        'message': 'Test message',
        'state': 'DONE'
    }
    nb_obj.dev = device
    nb_obj.post_device_status(**kw)
    mock_requests.put.assert_called_with(json={
        'message': kw['message'],
        'os_name': device.facts['os'],
        'ip_addr': device.target,
        'state': kw['state']
    },
        url='http://{}/api/devices/status'.format(args['server']))


def test_post_device_status_no_dev(nb_obj):
    nb_obj.log = MagicMock()
    message = 'test message'
    nb_obj.target = None
    nb_obj.post_device_status(message=message)
    nb_obj.log.error.assert_called_with('Either dev or target is required to post device status. Message was: {}'.format(message))


@patch('aeon_ztp.bin.nxos_bootstrap.NxosBootstrap.post_device_status')
def test_exit_results(mock_post, nb_obj, device):
    kw = {
        'results': {'ok': True},
        'exit_error': None,
    }
    with pytest.raises(SystemExit) as e:
        nb_obj.exit_results(**kw)
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
        nb_obj.exit_results(**kw)
    mock_post.assert_called_with(
        state='FAILED',
        message=kw['results']['message']
    )
    assert e.value.code == 1


@patch('aeon_ztp.bin.nxos_bootstrap.NxosBootstrap.exit_results', side_effect=SystemExit)
def test_wait_for_device_missing_username(mock_exit, cli_args, device):
    new_args = deepcopy(cli_args)
    new_args.user = None
    new_args.env_user = None
    with pytest.raises(SystemExit):
        nxos_bootstrap.NxosBootstrap(args['server'], new_args)
    mock_exit.assert_called_with(
        results={'ok': False,
                 'error_type': 'login',
                 'message': 'login user-name missing'}
    )


@patch('aeon_ztp.bin.nxos_bootstrap.NxosBootstrap.exit_results', side_effect=SystemExit)
def test_wait_for_device_missing_passwd(mock_exit, cli_args, device):
    new_args = deepcopy(cli_args)
    new_args.env_passwd = None
    with pytest.raises(SystemExit):
        nxos_bootstrap.NxosBootstrap(args['server'], new_args)
    mock_exit.assert_called_with(
        results={'ok': False,
                 'error_type': 'login',
                 'message': 'login user-password missing'}
    )


@patch('aeon_ztp.bin.nxos_bootstrap.time')
@patch('aeon_ztp.bin.nxos_bootstrap.NxosBootstrap.exit_results', side_effect=SystemExit)
@patch('aeon_ztp.bin.nxos_bootstrap.Device')
@patch('aeon_ztp.bin.nxos_bootstrap.NxosBootstrap.post_device_status')
def test_wait_for_device_probe_error(mock_post_dev, mock_dev, mock_exit, mock_time, nb_obj, device):
    mock_dev.side_effect = ProbeError()
    with pytest.raises(SystemExit):
        nb_obj.wait_for_device(2, 1)
    errmsg = 'Failed to probe target %s within reload countdown' % nb_obj.cli_args.target
    mock_exit.assert_called_with(
        exit_error=errmsg,
        results={'ok': False,
                 'error_type': 'login',
                 'message': errmsg
                 }
    )


@patch('aeon_ztp.bin.nxos_bootstrap.time')
@patch('aeon_ztp.bin.nxos_bootstrap.NxosBootstrap.exit_results', side_effect=SystemExit)
@patch('aeon_ztp.bin.nxos_bootstrap.Device')
@patch('aeon_ztp.bin.nxos_bootstrap.NxosBootstrap.post_device_status')
def test_wait_for_device_unauthorized_error(mock_post_dev, mock_dev, mock_exit, mock_time, nb_obj, device):
    mock_dev.side_effect = UnauthorizedError()
    with pytest.raises(SystemExit):
        nb_obj.wait_for_device(2, 1)
    errmsg = 'Unauthorized - check user/password'
    mock_exit.assert_called_with(
        exit_error=errmsg,
        results={'ok': False,
                 'error_type': 'login',
                 'message': errmsg
                 }
    )


@patch('aeon_ztp.bin.nxos_bootstrap.NxosBootstrap.exit_results', side_effect=SystemExit)
@patch('aeon_ztp.bin.nxos_bootstrap.time')
@patch('aeon_ztp.bin.nxos_bootstrap.Device')
@patch('aeon_ztp.bin.nxos_bootstrap.NxosBootstrap.post_device_facts')
def test_wait_for_device_failed_to_find_system(mock_post_facts, mock_dev, mock_time, mock_exit, nb_obj):
    poll_delay = 1
    mock_dev.return_value.api.exec_opcmd.return_value = ''
    with pytest.raises(SystemExit):
        nb_obj.wait_for_device(2, poll_delay)
    mock_exit.assert_called_with(
        results={
            'ok': False,
            'error_type': 'login',
            'message': '{} failed to find "System ready" within reload countdown'.format(nb_obj.cli_args.target)
        }
    )


@patch('aeon_ztp.bin.nxos_bootstrap.time')
@patch('aeon_ztp.bin.nxos_bootstrap.Device')
@patch('aeon_ztp.bin.nxos_bootstrap.NxosBootstrap.post_device_facts')
def test_wait_for_device(mock_post_facts, mock_dev, mock_time, nb_obj):
    poll_delay = 1
    mock_dev.return_value.api.exec_opcmd.return_value = 'CONF_CONTROL: System ready'
    nb_obj.wait_for_device(2, poll_delay)
    mock_dev.assert_has_calls([
        call(nb_obj.cli_args.target,
        passwd=os.environ['ENV_PASS'],
        timeout=poll_delay,
        user=nb_obj.cli_args.user or os.getenv(nb_obj.cli_args.env_user)),
        call().api.exec_opcmd("show logging | grep 'CONF_CONTROL: System ready'", msg_type='cli_show_ascii')

    ], any_order=True)
    mock_post_facts.assert_called()


# TODO: Mock out retry decorator
@pytest.mark.skip()
@patch('aeon_ztp.bin.nxos_bootstrap.NxosBootstrap.exit_results', side_effect=SystemExit)
@patch('aeon_ztp.bin.nxos_bootstrap.open')
@patch('aeon_ztp.bin.nxos_bootstrap.time')
@patch('aeon_ztp.bin.nxos_bootstrap.os.path.isfile', return_value=True)
def test_do_push_config_nxosexception(mock_isfile, mock_time, mock_open, mock_exit, device, nb_obj):
    mock_open.return_value.read.side_effect = ['all config', 'model config']
    errmsg = 'nxos error'
    device.api.exec_config.side_effect = NxExc.NxosException(errmsg)
    with pytest.raises(SystemExit):
        nb_obj.do_push_config()
    mock_exit.assert_called_with(
        dev=device,
        results={
            'ok': False,
            'error_type': 'config',
            'message': 'unable to push config: {}'.format(errmsg)
        }
    )


@patch('aeon_ztp.bin.nxos_bootstrap.retry')
@patch('aeon_ztp.bin.nxos_bootstrap.open')
@patch('aeon_ztp.bin.nxos_bootstrap.time')
@patch('aeon_ztp.bin.nxos_bootstrap.os.path.isfile', return_value=True)
def test_do_push_config(mock_isfile, mock_time, mock_open, mock_retry, device, nb_obj):
    mock_open.return_value.read.side_effect = ['all config', 'model config']
    nb_obj.dev = device
    nb_obj.do_push_config()
    device.api.exec_config.assert_has_calls([call('all config'), call('model config')], call('copy run start'))


@patch('aeon_ztp.bin.nxos_bootstrap.retry')
@patch('aeon_ztp.bin.nxos_bootstrap.open')
@patch('aeon_ztp.bin.nxos_bootstrap.time')
@patch('aeon_ztp.bin.nxos_bootstrap.os.path.isfile', return_value=False)
def test_do_push_config1_no_config(mock_isfile, mock_time, mock_open, mock_retry, device, nb_obj):
    mock_open.return_value.read.side_effect = ['all config', 'model config']
    nb_obj.dev = device
    nb_obj.do_push_config()
    assert not device.api.exec_config.called


@patch('aeon_ztp.bin.nxos_bootstrap.NxosBootstrap.exit_results', side_effect=SystemExit)
@patch('aeon_ztp.bin.nxos_bootstrap.json.loads')
@patch('aeon_ztp.bin.nxos_bootstrap.subprocess.Popen')
def test_check_os_install_json_exception(mock_subprocess, mock_json, mock_exit, nb_obj, device):
    nb_obj.dev = device
    test_stdout = 'test stdout'
    exception_msg = 'test exception message'
    errmsg = 'Unable to load os-select output as JSON: {}\n {}'.format(test_stdout, exception_msg)
    mock_json.side_effect = Exception(exception_msg)
    mock_subprocess.return_value.communicate.return_value = (test_stdout, 'test stderr')
    with pytest.raises(SystemExit):
        nb_obj.check_os_install_and_finally()
    mock_exit.assert_called_with(
        exit_error=errmsg,
        results={
            'ok': False,
            'error_type': 'install',
            'message': errmsg
        }
    )


@patch('aeon_ztp.bin.nxos_bootstrap.NxosBootstrap.exit_results', side_effect=SystemExit)
@patch('aeon_ztp.bin.nxos_bootstrap.subprocess.Popen')
def test_check_os_install(mock_subprocess, mock_exit, nb_obj, device):
    nb_obj.dev = device
    aztp_file = '{}/bin/aztp_os_selector.py'.format(nb_obj.cli_args.topdir)
    conf_fpath = '{}/etc/profiles/nxos/os-selector.cfg'.format(nb_obj.cli_args.topdir)
    facts = json.dumps(device.facts)
    json_string = '{"test_key": "test_value"}'
    mock_subprocess.return_value.communicate.return_value = (json_string, 'test stderr')
    results = nb_obj.check_os_install_and_finally()
    mock_subprocess.assert_called_with('{aztp_file} -j \'{facts}\' -c {conf_fpath}'.format(aztp_file=aztp_file,
                                                                                           facts=facts,
                                                                                           conf_fpath=conf_fpath),
                                       shell=True, stdout=-1)
    assert results == json.loads(json_string)


def test_ensure_md5sum_md5_exists(nb_obj):
    test_file = NamedTemporaryFile()
    test_md5_file = test_file.name + '.md5'
    copyfile(test_file.name, test_md5_file)
    with open(test_file.name, 'rb') as f:
        expected_md5sum = hashlib.md5(f.read()).hexdigest()
    with open(test_md5_file, 'a') as f:
        f.write(expected_md5sum)
    actual_md5sum = nb_obj.ensure_md5sum(test_file.name)
    assert expected_md5sum == actual_md5sum


def test_ensure_md5sum_md5_doesnt_exist(nb_obj):
    test_file = NamedTemporaryFile()
    with open(test_file.name, 'rb') as f:
        expected_md5sum = hashlib.md5(f.read()).hexdigest()
    actual_md5sum = nb_obj.ensure_md5sum(test_file.name)
    assert expected_md5sum == actual_md5sum


@patch('aeon_ztp.bin.nxos_bootstrap.NxosBootstrap.exit_results', side_effect=SystemExit)
@patch('aeon_ztp.bin.nxos_bootstrap.os.path.isfile', return_value=False)
def test_do_os_install_missing_image(mock_isfile, mock_exit, nb_obj, device):
    image_name = 'test_image'
    image_fpath = os.path.join(nb_obj.cli_args.topdir, 'vendor_images', device.facts['os'], image_name)
    errmsg = 'image file {} does not exist'.format(image_fpath)
    nb_obj.dev = device
    nb_obj.image_name = image_name
    with pytest.raises(SystemExit):
        nb_obj.do_os_install()
    mock_exit.assert_called_with(
        results={
            'ok': False,
            'error_type': 'install',
            'message': errmsg
        }
    )


@patch('aeon_ztp.bin.nxos_bootstrap.subprocess.Popen')
@patch('aeon_ztp.bin.nxos_bootstrap.NxosBootstrap.exit_results', side_effect=SystemExit)
@patch('aeon_ztp.bin.nxos_bootstrap.os.path.isfile', return_value=True)
def test_do_os_install(mock_isfile, mock_exit, mock_subprocess, nb_obj, device):
    image_name = 'nxos-1.1.1.1'
    image_md5 = '0899eaad7f62e995a5fd109839f926eb'
    nb_obj.dev = device
    nb_obj.image_name = image_name
    nb_obj.ensure_md5sum = Mock(return_value=image_md5)
    json_string = '{"test_key": "test_value"}'
    mock_subprocess.return_value.communicate.return_value = (json_string, 'test stderr')

    cmd_out = nb_obj.do_os_install()
    mock_subprocess.assert_called_with(
        "nxos-installos --target {target} --server {server} "
        "-U {u_env} -P {p_env} --image {image} --md5sum {md5sum} --logfile {logfile}".format(
            target=device.target, server=nb_obj.cli_args.server,
            u_env=nb_obj.cli_args.env_user, p_env=nb_obj.cli_args.env_passwd,
            image=image_name, md5sum=image_md5, logfile=nb_obj.cli_args.logfile),
        shell=True, stdout=-1)
    assert json.loads(json_string) == cmd_out


def test_do_ensure_os_version_no_install(device, nb_obj):
    nb_obj.dev = device
    nb_obj.check_os_install_and_finally = Mock()
    retval = nb_obj.do_ensure_os_version()
    assert retval == device


@patch('aeon_ztp.bin.nxos_bootstrap.NxosBootstrap.exit_results', side_effect=SystemExit)
@patch('aeon_ztp.bin.nxos_bootstrap.time')
def test_do_ensure_os_version_not_ok(mock_time, mock_exit, nb_obj, device):
    image_name = 'nxos-1.1.1.1'
    nb_obj.dev = device
    os_inst_ret = {'ok': False}

    def set_image_name(nb, image_name):
        nb.image_name = image_name
    nb_obj.check_os_install_and_finally = Mock(side_effect=set_image_name(nb_obj, image_name))
    nb_obj.do_os_install = Mock(return_value={'ok': False})
    nb_obj.wait_for_device = Mock(return_value=device)
    errmsg = 'software install [{ver}] FAILED: {reason}'.format(
        ver=image_name, reason=json.dumps(os_inst_ret))
    with pytest.raises(SystemExit):
        nb_obj.do_ensure_os_version()

    mock_exit.assert_called_with({
        'ok': False,
        'error_type': 'install',
        'message': errmsg
    })


@patch('aeon_ztp.bin.nxos_bootstrap.time')
def test_do_ensure_os_version(mock_time, nb_obj, device):
    image_name = 'nxos-1.1.1.1'
    nb_obj.dev = device

    def set_image_name(nb, image_name):
        nb.image_name = image_name
    nb_obj.check_os_install_and_finally = Mock(side_effect=set_image_name(nb_obj, image_name))
    nb_obj.do_os_install = Mock(return_value={'ok': True})
    nb_obj.wait_for_device = Mock(return_value=device)
    retval = nb_obj.do_ensure_os_version()

    nb_obj.do_os_install.assert_called()
    assert retval == device


@patch('aeon_ztp.bin.nxos_bootstrap.NxosBootstrap.exit_results', side_effect=SystemExit)
@patch('aeon_ztp.bin.nxos_bootstrap.os.path.isdir', return_value=False)
@patch('aeon_ztp.bin.nxos_bootstrap.cli_parse')
def test_main_no_topdir(mock_cli_parse, mock_is_dir, mock_exit, cli_args):
    mock_cli_parse.return_value = cli_args
    exc = '{} is not a directory'.format(cli_args.topdir)
    with pytest.raises(SystemExit):
        nxos_bootstrap.main()
    mock_exit.assert_called_with({'ok': False,
                                  'error_type': 'args',
                                  'message': exc})


@patch('aeon_ztp.bin.nxos_bootstrap.NxosBootstrap')
@patch('aeon_ztp.bin.nxos_bootstrap.NxosBootstrap.check_os_install_and_finally')
@patch('aeon_ztp.bin.nxos_bootstrap.NxosBootstrap.do_ensure_os_version')
@patch('aeon_ztp.bin.nxos_bootstrap.NxosBootstrap.wait_for_device')
@patch('aeon_ztp.bin.nxos_bootstrap.NxosBootstrap.exit_results', side_effect=SystemExit)
@patch('aeon_ztp.bin.nxos_bootstrap.os.path.isdir', return_value=True)
@patch('aeon_ztp.bin.nxos_bootstrap.time')
@patch('aeon_ztp.bin.nxos_bootstrap.cli_parse')
def test_main(mock_cli_parse, mock_time, mock_isdir, mock_exit, mock_wait, mock_ensure_os, mock_check_os_and_finally, mock_nb, cli_args, device, nb_obj):
    mock_cli_parse.return_value = cli_args
    mock_wait.return_value = device
    nb_obj.dev = device
    mock_nb.return_value = nb_obj
    with pytest.raises(SystemExit):
        nxos_bootstrap.main()
    mock_exit.assert_called_with({'ok': True})
    mock_wait.assert_called_with(countdown=cli_args.reload_delay, poll_delay=10)
    if device.facts['virtual']:
        assert not mock_ensure_os.called
    else:
        mock_ensure_os.assert_called()
