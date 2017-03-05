import pytest
import os
import mock
import json
import semver
from copy import deepcopy
from paramiko import AuthenticationException
from paramiko.ssh_exception import NoValidConnectionsError

from aeon_ztp.bin import ubuntu_bootstrap
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
    'os_name': 'ubuntu',
    'vendor': 'ubuntu',
    'hw_part_number': '1234',
    'hostname': 'ubuntu',
    'fqdn': 'ubuntu.localhost',
    'virtual': False,
    'service_tag': '1234',
    'os_version': '3.1.1',
    'hw_version': '1234',
    'mac_address': '0123456789012',
    'serial_number': '09786554',
    'hw_model': 's1000'
}

# Cumulus 2.x device
facts_v2 = dict(facts)
facts_v2['os_version'] = '2.5.7'

# Cumulus 3.1.2 device
facts_v312 = dict(facts)
facts_v312['os_version'] = '3.1.2'


@pytest.fixture()
def cli_args():

    parse = ubuntu_bootstrap.cli_parse(['--target', args['target'],
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
@pytest.fixture(params=[facts_v312, facts, facts_v2], ids=[
    'Cumulusv312',
    'Cumulusv311',
    'Cumulusv257'
])
def device(mock_con, request):
    dev = Device(args['target'], no_probe=True, no_gather_facts=True)
    dev.facts = request.param
    return dev


@pytest.fixture()
def ub_obj(cli_args):
    os.environ['ENV_PASS'] = 'admin'
    cb = ubuntu_bootstrap.UbuntuBootstrap(args['server'], cli_args)
    return cb


def test_cli_parse(cli_args):
    for arg in vars(cli_args):
        assert str(getattr(cli_args, arg)) == args[arg]


def test_ubuntu_bootstrap(cli_args, ub_obj):
    assert args['server'] == ub_obj.server
    assert cli_args == ub_obj.cli_args


@mock.patch('aeon_ztp.bin.ubuntu_bootstrap.requests')
def test_post_device_facts(mock_requests, device, ub_obj):
    ub_obj.post_device_facts(device)
    mock_requests.put.assert_called_with(json={
        'os_version': device.facts['os_version'],
        'os_name': ub_obj.os_name,
        'ip_addr': device.target,
        'hw_model': device.facts['hw_model'],
        'serial_number': device.facts['serial_number']
    },
        url='http://{}/api/devices/facts'.format(args['server']))


@mock.patch('aeon_ztp.bin.ubuntu_bootstrap.requests')
def test_post_device_status(mock_requests, device, ub_obj):
    kw = {
        'dev': device,
        'target': device.target,
        'message': 'Test message',
        'state': 'DONE'
    }
    ub_obj.post_device_status(**kw)
    mock_requests.put.assert_called_with(json={
        'message': kw['message'],
        'os_name': ub_obj.os_name,
        'ip_addr': device.target,
        'state': kw['state']
    },
        url='http://{}/api/devices/status'.format(args['server']))


@mock.patch('aeon_ztp.bin.ubuntu_bootstrap.UbuntuBootstrap.post_device_status')
def test_exit_results(mock_post, ub_obj, device):
    kw = {
        'results': {'ok': True},
        'dev': device,
        'target': device.target,
        'exit_error': None,
    }
    with pytest.raises(SystemExit) as e:
        ub_obj.exit_results(**kw)
    mock_post.assert_called_with(
        dev=kw['dev'],
        target=kw['target'],
        state='DONE',
        message='bootstrap completed OK'
    )
    assert e.value.code == 0

    # Test bad exit
    kw = {
        'results': {'ok': False,
                    'message': 'Error Message'},
        'dev': device,
        'target': device.target,
        'exit_error': 1,
    }
    with pytest.raises(SystemExit) as e:
        ub_obj.exit_results(**kw)
    mock_post.assert_called_with(
        dev=kw['dev'],
        target=kw['target'],
        state='ERROR',
        message=kw['results']['message']
    )
    assert e.value.code == 1


@mock.patch('aeon_ztp.bin.ubuntu_bootstrap.UbuntuBootstrap.exit_results', side_effect=SystemExit)
def test_wait_for_device_missing_username(mock_exit, cli_args, device):
    new_args = deepcopy(cli_args)
    new_args.user = None
    new_args.env_user = None
    local_cb = ubuntu_bootstrap.UbuntuBootstrap(args['server'], new_args)
    with pytest.raises(SystemExit):
        local_cb.wait_for_device(1, 2)
    mock_exit.assert_called_with(
        target=device.target,
        results={'ok': False,
                 'error_type': 'login',
                 'message': 'login user-name missing'}
    )


@mock.patch('aeon_ztp.bin.ubuntu_bootstrap.UbuntuBootstrap.exit_results', side_effect=SystemExit)
def test_wait_for_device_missing_passwd(mock_exit, cli_args, device):
    new_args = deepcopy(cli_args)
    new_args.env_passwd = None
    local_cb = ubuntu_bootstrap.UbuntuBootstrap(args['server'], new_args)
    with pytest.raises(SystemExit):
        local_cb.wait_for_device(1, 2)
    mock_exit.assert_called_with(
        target=device.target,
        results={'ok': False,
                 'error_type': 'login',
                 'message': 'login user-password missing'}
    )


@mock.patch('aeon_ztp.bin.ubuntu_bootstrap.UbuntuBootstrap.exit_results', side_effect=SystemExit)
@mock.patch('aeon_ztp.bin.ubuntu_bootstrap.Device', side_effect=AuthenticationException)
@mock.patch('aeon_ztp.bin.ubuntu_bootstrap.UbuntuBootstrap.post_device_status')
@mock.patch('aeon_ztp.bin.ubuntu_bootstrap.requests.put')
def test_wait_for_device_auth_exception(mock_requests, mock_post_dev, mock_dev, mock_exit, ub_obj):
    with pytest.raises(SystemExit):
        ub_obj.wait_for_device(1, 2)
    mock_exit.assert_called_with(
        target=ub_obj.cli_args.target,
        results={'ok': False,
                 'error_type': 'login',
                 'message': 'Unauthorized - check user/password'}
    )


@mock.patch('aeon_ztp.bin.ubuntu_bootstrap.time')
@mock.patch('aeon_ztp.bin.ubuntu_bootstrap.UbuntuBootstrap.exit_results', side_effect=SystemExit)
@mock.patch('aeon_ztp.bin.ubuntu_bootstrap.Device')
def test_wait_for_device_no_valid_connections(mock_dev, mock_exit, mock_time, ub_obj):
    mock_dev.side_effect = NoValidConnectionsError({'error': 'test error value'})
    with pytest.raises(SystemExit):
        ub_obj.wait_for_device(2, 1)
    mock_exit.assert_called_with(
        target=ub_obj.cli_args.target,
        results={'ok': False,
                 'error_type': 'login',
                 'message': 'Failed to connect to target %s within reload countdown' % ub_obj.cli_args.target}
    )


@mock.patch('aeon_ztp.bin.ubuntu_bootstrap.UbuntuBootstrap.post_device_facts')
@mock.patch('aeon_ztp.bin.ubuntu_bootstrap.Device')
def test_wait_for_device(mock_dev, mock_post_facts, ub_obj):
    poll_delay = 2
    dev = ub_obj.wait_for_device(1, poll_delay)
    mock_dev.assert_called_with(
        ub_obj.cli_args.target,
        passwd=os.environ['ENV_PASS'],
        timeout=poll_delay,
        user=ub_obj.cli_args.user or os.getenv(ub_obj.cli_args.env_user)
    )
    mock_post_facts.assert_called_with(
        dev
    )


@mock.patch('aeon_ztp.bin.ubuntu_bootstrap.subprocess')
@mock.patch('aeon_ztp.bin.ubuntu_bootstrap.UbuntuBootstrap.exit_results', side_effect=SystemExit)
def test_get_required_os_exception(mock_exit_results, mock_subprocess, device):
    mock_subprocess.Popen.return_value.communicate.return_value = ('stdout', 'stderr')
    local_cb = ubuntu_bootstrap.UbuntuBootstrap(args['server'], cli_args())
    with pytest.raises(SystemExit):
        local_cb.get_required_os(device)
    mock_exit_results.assert_called_with(dev=device,
                                         results={'message': 'Unable to load os-select output as JSON: stdout',
                                                  'error_type': 'install',
                                                  'ok': False})


@mock.patch('aeon_ztp.bin.ubuntu_bootstrap.subprocess.Popen')
def test_get_required_os(mock_subprocess, device):
    expected_os_sel_output = '{"output": "os-select test output"}'
    mock_subprocess.return_value.communicate.return_value = (expected_os_sel_output, 'stderr')
    local_cb = ubuntu_bootstrap.UbuntuBootstrap(args['server'], cli_args())
    conf_fpath = '{topdir}/etc/profiles/default/ubuntu/os-selector.cfg'.format(topdir=cli_args().topdir)
    cmd = "{topdir}/bin/aztp_os_selector.py -j '{dev_json}' -c {config}".format(topdir=cli_args().topdir,
                                                                                dev_json=json.dumps(device.facts),
                                                                                config=conf_fpath)
    os_sel_output = local_cb.get_required_os(device)
    assert os_sel_output == json.loads(expected_os_sel_output)
    mock_subprocess.assert_called_with(cmd, shell=True, stdout=-1)


@mock.patch('aeon_ztp.bin.ubuntu_bootstrap.os.path.exists', return_value=False)
@mock.patch('aeon_ztp.bin.ubuntu_bootstrap.UbuntuBootstrap.exit_results', side_effect=SystemExit)
def test_install_os_image_missing(mock_exit_results, mock_os, ub_obj, device):
    image_name = 'test_image'
    image_fpath = os.path.join(ub_obj.cli_args.topdir, 'vendor_images', ub_obj.os_name, image_name)
    errmsg = 'image file does not exist: {}'.format(image_fpath)
    with pytest.raises(SystemExit):
        ub_obj.install_os(device, image_name)
    mock_exit_results.assert_called_with(dev=device,
                                         results={'ok': False,
                                                  'error_type': 'install',
                                                  'message': errmsg}
                                         )


@mock.patch('aeon.cumulus.device.Connector')
@mock.patch('aeon_ztp.bin.ubuntu_bootstrap.os.path.exists', return_value=True)
@mock.patch('aeon_ztp.bin.ubuntu_bootstrap.UbuntuBootstrap.exit_results', side_effect=SystemExit)
def test_install_os_image_not_all_good(mock_exit_results, mock_os, mock_con, device, cli_args):
    image_name = 'test_image'
    errmsg = 'error running command'
    device.api.execute.return_value = (False, errmsg)
    local_cb = ubuntu_bootstrap.UbuntuBootstrap(args['server'], cli_args)

    cmd = 'sudo /usr/cumulus/bin/cl-img-install -sf http://{server}/images/{os_name}/{image_name}'.format(
          server=local_cb.cli_args.server, os_name=local_cb.os_name, image_name=image_name)

    with pytest.raises(SystemExit):
        local_cb.install_os(device, image_name)
    mock_exit_results.assert_called_with(dev=device,
                                         results={
                                             'ok': False,
                                             'error_type': 'install',
                                             'message': 'Unable to run command: {cmd}. '
                                             'Error message: {errmsg}'.format(cmd=cmd, errmsg=errmsg)
                                         })


@mock.patch('aeon_ztp.bin.ubuntu_bootstrap.UbuntuBootstrap.wait_for_device')
@mock.patch('aeon_ztp.bin.ubuntu_bootstrap.time')
@mock.patch('aeon.cumulus.device.Connector')
@mock.patch('aeon_ztp.bin.ubuntu_bootstrap.os.path.exists', return_value=True)
def test_install_os_image(mock_os, mock_con, mock_time, mock_wait_device, device, cli_args):
    image_name = 'test_image'
    results = 'test result message'
    device.api.execute.return_value = (True, results)
    local_cb = ubuntu_bootstrap.UbuntuBootstrap(args['server'], cli_args)

    cmd = 'sudo /usr/cumulus/bin/cl-img-install -sf http://{server}/images/{os_name}/{image_name}'.format(
          server=local_cb.cli_args.server, os_name=local_cb.os_name, image_name=image_name)
    method_calls = [mock.call.execute([cmd])]

    local_cb.install_os(device, image_name)
    assert device.api.method_calls == method_calls


@mock.patch('aeon_ztp.bin.ubuntu_bootstrap.time')
@mock.patch('aeon_ztp.bin.ubuntu_bootstrap.UbuntuBootstrap.install_os')
@mock.patch('aeon_ztp.bin.ubuntu_bootstrap.UbuntuBootstrap.get_required_os')
@mock.patch('aeon_ztp.bin.ubuntu_bootstrap.UbuntuBootstrap.wait_for_device')
def test_ensure_os_version(mock_wait_for_device, mock_get_os, mock_install_os, mock_time, device, cli_args):
    results = 'test result message'
    device.api.execute.return_value = (True, results)
    ver_required = '3.1.2'
    image_name = 'image_file_name'

    def mock_get_os_function(dev):
        diff = semver.compare(dev.facts['os_version'], ver_required)
        # Check if upgrade is required
        if diff < 0:
            # upgrade required
            return {'image': image_name}
        else:
            # upgrade not required
            return {'image': None}
    mock_get_os.side_effect = mock_get_os_function
    local_cb = ubuntu_bootstrap.UbuntuBootstrap(args['server'], cli_args)
    local_cb.ensure_os_version(device)

    # If upgrade was required, check that the correct calls were made
    if mock_get_os_function(device)['image']:
        assert mock_install_os.called_with(mock.call(device), image_name=image_name)

        device.api.execute.assert_called_with(['sudo reboot'])
        mock_wait_for_device.assert_called_with(countdown=local_cb.cli_args.reload_delay, poll_delay=10)

    else:
        assert not device.api.execute.called
        assert not mock_install_os.called


@mock.patch('aeon_ztp.bin.ubuntu_bootstrap.UbuntuBootstrap.exit_results', side_effect=SystemExit)
@mock.patch('aeon_ztp.bin.ubuntu_bootstrap.os.path.isdir', return_value=False)
@mock.patch('aeon_ztp.bin.ubuntu_bootstrap.time')
@mock.patch('aeon_ztp.bin.ubuntu_bootstrap.cli_parse')
def test_main_invalid_topdir(mock_cli_parse, mock_time, mock_isdir, mock_exit, cli_args):
    mock_cli_parse.return_value = cli_args
    exc = '{} is not a directory'.format(cli_args.topdir)
    with pytest.raises(SystemExit):
        ubuntu_bootstrap.main()
    mock_exit.assert_called_with({'ok': False,
                                  'error_type': 'args',
                                  'message': exc})


@mock.patch('aeon_ztp.bin.ubuntu_bootstrap.UbuntuBootstrap.ensure_os_version')
@mock.patch('aeon_ztp.bin.ubuntu_bootstrap.UbuntuBootstrap.wait_for_device')
@mock.patch('aeon_ztp.bin.ubuntu_bootstrap.UbuntuBootstrap.exit_results', side_effect=SystemExit)
@mock.patch('aeon_ztp.bin.ubuntu_bootstrap.os.path.isdir', return_value=True)
@mock.patch('aeon_ztp.bin.ubuntu_bootstrap.time')
@mock.patch('aeon_ztp.bin.ubuntu_bootstrap.cli_parse')
def test_main(mock_cli_parse, mock_time, mock_isdir, mock_exit, mock_wait, mock_ensure_os, cli_args, device):
    mock_cli_parse.return_value = cli_args
    mock_wait.return_value = device
    with pytest.raises(SystemExit):
        ubuntu_bootstrap.main()
    mock_exit.assert_called_with({'ok': True},
                                 dev=device)
    mock_wait.assert_called_with(countdown=cli_args.reload_delay, poll_delay=10)
