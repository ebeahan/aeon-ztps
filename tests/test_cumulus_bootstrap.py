import pytest
import os
import mock
import json
import semver
from copy import deepcopy
from paramiko import AuthenticationException
from paramiko.ssh_exception import NoValidConnectionsError
from pexpect.pxssh import ExceptionPxssh

from aeon_ztp.bin import cumulus_bootstrap
from aeon.cumulus.device import Device

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

facts = {
    'os_name': 'cumulus',
    'vendor': 'cumulus',
    'hw_part_number': '1234',
    'hostname': 'cumulus',
    'fqdn': 'cumulus.localhost',
    'virtual': False,
    'service_tag': '1234',
    'os_version': '3.1.1',
    'hw_version': '1234',
    'mac_address': '0123456789012',
    'serial_number': '09786554',
    'hw_model': 'c1000'
}

# Cumulus 2.x device
facts_v2 = dict(facts)
facts_v2['os_version'] = '2.5.7'

# Cumulus 3.1.2 device
facts_v312 = dict(facts)
facts_v312['os_version'] = '3.1.2'

# Cumulus VX
facts_cvx = dict(facts)
facts_cvx['virtual'] = True
_OS_NAME = 'cumulus'


@pytest.fixture()
def cli_args():

    parse = cumulus_bootstrap.cli_parse(['--target', args['target'],
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
    mock_response = mock.MagicMock()
    monkeypatch.setattr('requests.sessions.Session.request', mock_response)


@mock.patch('aeon.cumulus.device.Connector')
# Parametrize device to test Cumulus v2, v3.1.1, v3.1.2, and VX
@pytest.fixture(params=[facts_v312, facts, facts_v2, facts_cvx], ids=['Cumulusv312',
                                                                      'Cumulusv311',
                                                                      'Cumulusv257',
                                                                      'CumulusVX'])
def device(mock_con, request):
    dev = Device(args['target'], no_probe=True, no_gather_facts=True)
    dev.facts = request.param
    return dev


@pytest.fixture()
def cb_obj(cli_args):
    os.environ['ENV_PASS'] = 'admin'
    cb = cumulus_bootstrap.CumulusBootstrap(args['server'], cli_args)
    return cb


def test_cli_parse(cli_args):
    for arg in vars(cli_args):
        assert str(getattr(cli_args, arg)) == args[arg]


def test_cumulus_bootstrap(cli_args, cb_obj):
    assert args['server'] == cb_obj.server
    assert cli_args == cb_obj.cli_args


@mock.patch('aeon_ztp.bin.cumulus_bootstrap.requests')
def test_post_device_facts(mock_requests, device, cb_obj):
    cb_obj.dev = device
    cb_obj.post_device_facts()
    mock_requests.put.assert_called_with(json={
        'os_version': device.facts['os_version'],
        'os_name': device.facts['os_name'],
        'ip_addr': device.target,
        'hw_model': device.facts['hw_model'],
        'serial_number': device.facts['serial_number'],
        'facts': json.dumps(device.facts),
        'image_name': None,
        'finally_script': None
    },
        url='http://{}/api/devices/facts'.format(args['server']))


@mock.patch('aeon_ztp.bin.cumulus_bootstrap.requests')
def test_post_device_status(mock_requests, device, cb_obj):
    kw = {
        'message': 'Test message',
        'state': 'DONE'
    }
    cb_obj.dev = device
    cb_obj.post_device_status(**kw)
    mock_requests.put.assert_called_with(json={
        'message': kw['message'],
        'os_name': device.facts['os_name'],
        'ip_addr': device.target,
        'state': kw['state']
    },
        url='http://{}/api/devices/status'.format(args['server']))


@mock.patch('aeon_ztp.bin.cumulus_bootstrap.CumulusBootstrap.post_device_status')
def test_exit_results(mock_post, cb_obj, device):
    kw = {
        'results': {'ok': True},
        'exit_error': None,
    }
    with pytest.raises(SystemExit) as e:
        cb_obj.exit_results(**kw)
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
        cb_obj.exit_results(**kw)
    mock_post.assert_called_with(
        state='FAILED',
        message=kw['results']['message']
    )
    assert e.value.code == 1


@mock.patch('aeon_ztp.bin.cumulus_bootstrap.CumulusBootstrap.exit_results', side_effect=SystemExit)
def test_wait_for_device_missing_username(mock_exit, cli_args, device):
    new_args = deepcopy(cli_args)
    new_args.user = None
    new_args.env_user = None
    with pytest.raises(SystemExit):
        cumulus_bootstrap.CumulusBootstrap(args['server'], new_args)
    mock_exit.assert_called_with(
        results={'ok': False,
                 'error_type': 'login',
                 'message': 'login user-name missing'}
    )


@mock.patch('aeon_ztp.bin.cumulus_bootstrap.CumulusBootstrap.exit_results', side_effect=SystemExit)
def test_wait_for_device_missing_passwd(mock_exit, cli_args, device):
    new_args = deepcopy(cli_args)
    new_args.env_passwd = None
    with pytest.raises(SystemExit):
        cumulus_bootstrap.CumulusBootstrap(args['server'], new_args)
    mock_exit.assert_called_with(
        results={'ok': False,
                 'error_type': 'login',
                 'message': 'login user-password missing'}
    )


@mock.patch('aeon_ztp.bin.cumulus_bootstrap.CumulusBootstrap.exit_results', side_effect=SystemExit)
@mock.patch('aeon_ztp.bin.cumulus_bootstrap.Device', side_effect=AuthenticationException)
@mock.patch('aeon_ztp.bin.cumulus_bootstrap.CumulusBootstrap.post_device_status')
@mock.patch('aeon_ztp.bin.cumulus_bootstrap.requests.put')
def test_wait_for_device_auth_exception(mock_requests, mock_post_dev, mock_dev, mock_exit, cb_obj):
    with pytest.raises(SystemExit):
        cb_obj.wait_for_device(1, 2)
    mock_exit.assert_called_with(
        results={'ok': False,
                 'error_type': 'login',
                 'message': 'Unauthorized - check user/password'}
    )


@mock.patch('aeon_ztp.bin.cumulus_bootstrap.time')
@mock.patch('aeon_ztp.bin.cumulus_bootstrap.CumulusBootstrap.exit_results', side_effect=SystemExit)
@mock.patch('aeon_ztp.bin.cumulus_bootstrap.Device')
def test_wait_for_device_no_valid_connections(mock_dev, mock_exit, mock_time, cb_obj):
    mock_dev.side_effect = NoValidConnectionsError({'error': 'test error value'})
    with pytest.raises(SystemExit):
        cb_obj.wait_for_device(2, 1)
    mock_exit.assert_called_with(
        results={'ok': False,
                 'error_type': 'login',
                 'message': 'Failed to connect to target %s within reload countdown' % cb_obj.cli_args.target}
    )


@mock.patch('aeon_ztp.bin.cumulus_bootstrap.CumulusBootstrap.post_device_facts')
@mock.patch('aeon_ztp.bin.cumulus_bootstrap.Device')
def test_wait_for_device(mock_dev, mock_post_facts, cb_obj):
    poll_delay = 2
    cb_obj.wait_for_device(1, poll_delay)
    mock_dev.assert_called_with(
        cb_obj.cli_args.target,
        passwd=os.environ['ENV_PASS'],
        timeout=poll_delay,
        user=cb_obj.cli_args.user or os.getenv(cb_obj.cli_args.env_user)
    )
    mock_post_facts.assert_called()


@mock.patch('aeon_ztp.bin.cumulus_bootstrap.pxssh')
def test_wait_for_onie_rescue(mock_pxssh, cb_obj):
    countdown = 5
    poll_delay = 1
    user = 'root'
    pxssh_calls = [mock.call.pxssh(options={'UserKnownHostsFile': '/dev/null', 'StrictHostKeyChecking': 'no'}),
                   mock.call.pxssh().login(cb_obj.cli_args.target, user, auto_prompt_reset=False),
                   mock.call.pxssh().sendline('\n'),
                   mock.call.pxssh().prompt()]
    wait = cb_obj.wait_for_onie_rescue(countdown, poll_delay, user=user)
    assert wait
    mock_pxssh.assert_has_calls(pxssh_calls)


@mock.patch('aeon_ztp.bin.cumulus_bootstrap.time')
@mock.patch('aeon_ztp.bin.cumulus_bootstrap.CumulusBootstrap.exit_results', side_effect=SystemExit)
@mock.patch('aeon_ztp.bin.cumulus_bootstrap.CumulusBootstrap.post_device_status')
@mock.patch('aeon_ztp.bin.cumulus_bootstrap.pxssh.pxssh')
def test_wait_for_onie_rescue_pxsshexception(mock_pxssh, mock_post_dev, mock_exit_results, mock_time):
    mock_pxssh.return_value.login.side_effect = ExceptionPxssh('Could not establish connection to host')
    countdown = 1
    poll_delay = 1
    user = 'root'
    mock_post_dev_calls = [mock.call(message='Cumulus installation in progress. Waiting for boot to ONIE rescue mode. '
                                             'Timeout remaining: 1 seconds',
                                     state='AWAIT-ONLINE'),
                           mock.call(message='Cumulus installation in progress. Waiting for boot to ONIE rescue mode. '
                                             'Timeout remaining: 0 seconds',
                                     state='AWAIT-ONLINE')
                           ]
    local_cb = cumulus_bootstrap.CumulusBootstrap(args['server'], cli_args())
    with pytest.raises(SystemExit):
        local_cb.wait_for_onie_rescue(countdown, poll_delay, user=user)
    mock_post_dev.assert_has_calls(mock_post_dev_calls)
    mock_exit_results.assert_called_with(results={'message': 'Device 1.1.1.1 not reachable in ONIE rescue mode within reload countdown.',
                                                  'error_type': 'login',
                                                  'ok': False})


@mock.patch('aeon_ztp.bin.cumulus_bootstrap.CumulusBootstrap.exit_results', side_effect=SystemExit)
@mock.patch('aeon_ztp.bin.cumulus_bootstrap.CumulusBootstrap.post_device_status')
@mock.patch('aeon_ztp.bin.cumulus_bootstrap.pxssh.pxssh')
def test_wait_for_onie_rescue_exception(mock_pxssh, mock_post_dev, mock_exit_results):
    error = 'Super weird error youve never seen before'
    mock_pxssh.return_value.login.side_effect = ExceptionPxssh(error)
    countdown = 1
    poll_delay = 1
    user = 'root'
    target = cli_args().target
    mock_post_dev_calls = [mock.call(message='Cumulus installation in progress. Waiting for boot to ONIE rescue mode. '
                                             'Timeout remaining: 1 seconds',
                                     state='AWAIT-ONLINE')
                           ]
    local_cb = cumulus_bootstrap.CumulusBootstrap(args['server'], cli_args())
    with pytest.raises(SystemExit):
        local_cb.wait_for_onie_rescue(countdown, poll_delay, user=user)
    mock_post_dev.assert_has_calls(mock_post_dev_calls)
    mock_exit_results.assert_called_with(results={'message': 'Error accessing {target} in ONIE rescue'
                                                             ' mode: {error}.'.format(target=target, error=error),
                                                  'error_type': 'login',
                                                  'ok': False}
                                         )


@mock.patch('aeon_ztp.bin.cumulus_bootstrap.CumulusBootstrap.exit_results', side_effect=SystemExit)
@mock.patch('aeon_ztp.bin.cumulus_bootstrap.json.loads')
@mock.patch('aeon_ztp.bin.cumulus_bootstrap.subprocess.Popen')
def test_check_os_install_json_exception(mock_subprocess, mock_json, mock_exit, cb_obj, device):
    cb_obj.dev = device
    test_stdout = 'test stdout'
    exception_msg = 'test exception message'
    errmsg = 'Unable to load os-select output as JSON: {}\n {}'.format(test_stdout, exception_msg)
    mock_json.side_effect = Exception(exception_msg)
    mock_subprocess.return_value.communicate.return_value = (test_stdout, 'test stderr')
    with pytest.raises(SystemExit):
        cb_obj.check_os_install_and_finally()
    mock_exit.assert_called_with(
        exit_error=errmsg,
        results={
            'ok': False,
            'error_type': 'install',
            'message': errmsg
        }
    )


@mock.patch('aeon_ztp.bin.cumulus_bootstrap.subprocess.Popen')
def test_get_required_os(mock_subprocess, device):
    expected_os_sel_output = '{"output": "os-select test output"}'
    mock_subprocess.return_value.communicate.return_value = (expected_os_sel_output, 'stderr')
    local_cb = cumulus_bootstrap.CumulusBootstrap(args['server'], cli_args())
    local_cb.dev = device
    conf_fpath = '{topdir}/etc/profiles/cumulus/os-selector.cfg'.format(topdir=cli_args().topdir)
    cmd = "{topdir}/bin/aztp_os_selector.py -j '{dev_json}' -c {config}".format(topdir=cli_args().topdir,
                                                                                dev_json=json.dumps(device.facts),
                                                                                config=conf_fpath)
    os_sel_output = local_cb.check_os_install_and_finally()
    assert os_sel_output == json.loads(expected_os_sel_output)
    mock_subprocess.assert_called_with(cmd, shell=True, stdout=-1)


@mock.patch('aeon_ztp.bin.cumulus_bootstrap.CumulusBootstrap.exit_results', side_effect=SystemExit)
@mock.patch('aeon_ztp.bin.cumulus_bootstrap.pxssh.pxssh')
def test_onie_install_pxssh_exception(mock_pxssh, mock_exit_results, cb_obj, device):
    cb_obj.dev = device
    exc = ExceptionPxssh('Could not establish connection to host')
    mock_pxssh.return_value.login.side_effect = exc
    with pytest.raises(SystemExit):
        cb_obj.onie_install()
    mock_exit_results.assert_called_with(results={'ok': False,
                                                  'error_type': 'install',
                                                  'message': exc})


@mock.patch('aeon_ztp.bin.cumulus_bootstrap.time')
@mock.patch('aeon_ztp.bin.cumulus_bootstrap.pxssh.pxssh')
def test_onie_install_pxssh(mock_pxssh, mock_time, cb_obj, device):
    cb_obj.dev = device
    user = 'test'
    image_name = 'test_image'
    cb_obj.image_name = image_name
    pxssh_calls = [mock.call().pxssh(options={'UserKnownHostsFile': '/dev/null', 'StrictHostKeyChecking': 'no'}),
                   mock.call().login(cb_obj.cli_args.target, user, auto_prompt_reset=False),
                   mock.call().sendline('\n'),
                   mock.call().prompt(),
                   mock.call().sendline('onie-nos-install http://{server}/images/{os_name}/{image_name}'.format(
                       server=cb_obj.cli_args.server, os_name=_OS_NAME, image_name=image_name)),
                   mock.call().expect('installer', timeout=15),
                   mock.call().expect('Please reboot to start installing OS.', timeout=180),
                   mock.call().prompt(),
                   mock.call().sendline('reboot'),
                   mock.call().close()]
    success = cb_obj.onie_install(user=user)
    assert success
    assert mock_pxssh.mock_calls == pxssh_calls


@mock.patch('aeon_ztp.bin.cumulus_bootstrap.os.path.exists', return_value=False)
@mock.patch('aeon_ztp.bin.cumulus_bootstrap.CumulusBootstrap.exit_results', side_effect=SystemExit)
def test_install_os_image_missing(mock_exit_results, mock_os, cb_obj, device):
    image_name = 'test_image'
    cb_obj.image_name = image_name
    image_fpath = os.path.join(cb_obj.cli_args.topdir, 'vendor_images', _OS_NAME, image_name)
    errmsg = 'image file does not exist: {}'.format(image_fpath)
    with pytest.raises(SystemExit):
        cb_obj.install_os()
    mock_exit_results.assert_called_with(results={'ok': False,
                                                  'error_type': 'install',
                                                  'message': errmsg}
                                         )


@mock.patch('aeon.cumulus.device.Connector')
@mock.patch('aeon_ztp.bin.cumulus_bootstrap.os.path.exists', return_value=True)
@mock.patch('aeon_ztp.bin.cumulus_bootstrap.CumulusBootstrap.exit_results', side_effect=SystemExit)
def test_install_os_image_not_all_good(mock_exit_results, mock_os, mock_con, device, cli_args):
    image_name = 'test_image'
    errmsg = 'error running command'
    device.api.execute.return_value = (False, errmsg)
    local_cb = cumulus_bootstrap.CumulusBootstrap(args['server'], cli_args)
    local_cb.dev = device
    local_cb.image_name = image_name

    sem_ver = semver.parse_version_info(device.facts['os_version'])
    if sem_ver >= (3, 0, 0):
        # Cumulus 3.x install command
        cmd = 'sudo onie-select -rf'
    else:
        # Cumulus 2.x install command
        cmd = 'sudo /usr/cumulus/bin/cl-img-install -sf http://{server}/images/{os_name}/{image_name}'.format(
            server=local_cb.cli_args.server, os_name=_OS_NAME, image_name=image_name)

    with pytest.raises(SystemExit):
        local_cb.install_os()
    mock_exit_results.assert_called_with(results={'ok': False,
                                                  'error_type': 'install',
                                                  'message': 'Unable to run command: {cmd}. '
                                                             'Error message: {errmsg}'.format(cmd=cmd, errmsg=errmsg)})


@mock.patch('aeon_ztp.bin.cumulus_bootstrap.CumulusBootstrap.wait_for_onie_rescue')
@mock.patch('aeon_ztp.bin.cumulus_bootstrap.CumulusBootstrap.onie_install')
@mock.patch('aeon_ztp.bin.cumulus_bootstrap.CumulusBootstrap.wait_for_device')
@mock.patch('aeon_ztp.bin.cumulus_bootstrap.time')
@mock.patch('aeon.cumulus.device.Connector')
@mock.patch('aeon_ztp.bin.cumulus_bootstrap.os.path.exists', return_value=True)
def test_install_os_image(mock_os, mock_con, mock_time, mock_wait_device,
                          mock_onie_install, mock_wait_for_onie, device, cli_args):
    image_name = 'test_image'
    results = 'test result message'
    device.api.execute.return_value = (True, results)
    local_cb = cumulus_bootstrap.CumulusBootstrap(args['server'], cli_args)
    local_cb.dev = device
    local_cb.image_name = image_name

    sem_ver = semver.parse_version_info(device.facts['os_version'])
    if sem_ver >= (3, 0, 0):
        # Cumulus 3.x install command
        cmd = 'sudo onie-select -rf'
        method_calls = [mock.call.execute([cmd]), mock.call.execute(['sudo reboot'])]
    else:
        # Cumulus 2.x install command
        cmd = 'sudo /usr/cumulus/bin/cl-img-install -sf http://{server}/images/{os_name}/{image_name}'.format(
            server=local_cb.cli_args.server, os_name=_OS_NAME, image_name=image_name)
        method_calls = [mock.call.execute([cmd])]

    local_cb.install_os()
    assert device.api.method_calls == method_calls


@mock.patch('aeon_ztp.bin.cumulus_bootstrap.time')
@mock.patch('aeon_ztp.bin.cumulus_bootstrap.CumulusBootstrap.install_os')
@mock.patch('aeon_ztp.bin.cumulus_bootstrap.CumulusBootstrap.check_os_install_and_finally')
@mock.patch('aeon_ztp.bin.cumulus_bootstrap.CumulusBootstrap.wait_for_device')
def test_ensure_os_version(mock_wait_for_device, mock_get_os, mock_install_os, mock_time, device, cli_args):
    results = 'test result message'
    device.api.execute.return_value = (True, results)
    ver_required = '3.1.2'
    device_semver = semver.parse_version_info(device.facts['os_version'])
    image_name = 'image_file_name'

    def mock_get_os_function():
        diff = semver.compare(device.facts['os_version'], ver_required)
        # Check if upgrade is required
        if diff < 0:
            # upgrade required
            local_cb.image_name = image_name
        else:
            # upgrade not required
            local_cb.image_name = None
    mock_get_os.side_effect = mock_get_os_function
    local_cb = cumulus_bootstrap.CumulusBootstrap(args['server'], cli_args)
    local_cb.dev = device
    local_cb.ensure_os_version()

    # If upgrade was required, check that the correct calls were made
    if local_cb.image_name:
        assert mock_install_os.called_with(mock.call(device), image_name=image_name)
        if device_semver < (3, 0, 0):
            device.api.execute.assert_called_with(['sudo reboot'])
            mock_wait_for_device.assert_called_with(countdown=local_cb.cli_args.reload_delay, poll_delay=10)
        else:
            # Ensure device was not rebooted if v3 or greater, and wait_for_device was called
            assert not device.api.execute.called
    else:
        assert not device.api.execute.called
        assert not mock_install_os.called


@mock.patch('aeon_ztp.bin.cumulus_bootstrap.CumulusBootstrap.exit_results', side_effect=SystemExit)
@mock.patch('aeon_ztp.bin.cumulus_bootstrap.os.path.isdir', return_value=False)
@mock.patch('aeon_ztp.bin.cumulus_bootstrap.time')
@mock.patch('aeon_ztp.bin.cumulus_bootstrap.cli_parse')
def test_main_invalid_topdir(mock_cli_parse, mock_time, mock_isdir, mock_exit, cli_args):
    mock_cli_parse.return_value = cli_args
    exc = '{} is not a directory'.format(cli_args.topdir)
    with pytest.raises(SystemExit):
        cumulus_bootstrap.main()
    mock_exit.assert_called_with({'ok': False,
                                  'error_type': 'args',
                                  'message': exc})


@mock.patch('aeon_ztp.bin.cumulus_bootstrap.CumulusBootstrap')
@mock.patch('aeon_ztp.bin.cumulus_bootstrap.CumulusBootstrap.check_os_install_and_finally')
@mock.patch('aeon_ztp.bin.cumulus_bootstrap.CumulusBootstrap.ensure_os_version')
@mock.patch('aeon_ztp.bin.cumulus_bootstrap.CumulusBootstrap.wait_for_device')
@mock.patch('aeon_ztp.bin.cumulus_bootstrap.CumulusBootstrap.exit_results', side_effect=SystemExit)
@mock.patch('aeon_ztp.bin.cumulus_bootstrap.os.path.isdir', return_value=True)
@mock.patch('aeon_ztp.bin.cumulus_bootstrap.time')
@mock.patch('aeon_ztp.bin.cumulus_bootstrap.cli_parse')
def test_main(mock_cli_parse, mock_time, mock_isdir, mock_exit, mock_wait, mock_ensure_os, mock_check_os_and_finally, mock_cb, cli_args, device, cb_obj):
    mock_cli_parse.return_value = cli_args
    mock_wait.return_value = device
    cb_obj.dev = device
    mock_cb.return_value = cb_obj

    with pytest.raises(SystemExit):
        cumulus_bootstrap.main()
    mock_exit.assert_called_with({'ok': True})
    mock_wait.assert_called_with(countdown=cli_args.reload_delay, poll_delay=10, msg='Waiting for device access')
    if device.facts['virtual']:
        assert not mock_ensure_os.called
    else:
        mock_ensure_os.assert_called
