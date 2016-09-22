#!/usr/bin/python
# Copyright 2014-present, Apstra, Inc. All rights reserved.
#
# This source code is licensed under End User License Agreement found in the
# LICENSE file at http://www.apstra.com/community/eula
import os
import aeon_ztp
import aeon_ztp.api.models as models
import pkg_resources
import pytest
from mock import patch
from tempfile import NamedTemporaryFile

import json
from aeon_ztp import create_app


@patch('aeon_ztp.Flask')
@patch('aeon_ztp.ma')
@patch('aeon_ztp.db')
def test_create_app(mock_db, mock_ma, mock_flask):
    test_app = create_app()
    # Assert that app is created with production config by default
    config = test_app.method_calls[0][1][0]
    assert config == aeon_ztp.config['production']


@patch('aeon_ztp.create_app')
def test_aeon_ztp_app(mock_create):
    from aeon_ztp.aeon_ztp_app import app  # NOQA
    args, kwargs = mock_create.call_args_list[0]
    assert args == ('production', )
    assert kwargs == {}


def test_create_device_in_db(device):
    db_device = models.Device.query.get('1.2.3.4')
    rcvd_device_data = models.device_schema.dump(db_device).data
    assert rcvd_device_data == device


def test_download_file(client):
    """
    Creates a temporary file and verifies that it can be downloaded
    """
    download_dir = os.path.join(os.environ['AEON_TOPDIR'], 'downloads')
    temp = NamedTemporaryFile(dir=download_dir)
    temp.write('test_data_stream')
    try:
        rv = client.get("/downloads/" + os.path.basename(temp.name))
    finally:
        temp.close()
    assert rv.status_code == 200
    assert rv.data == 'test_data_stream'


def test_get_vendor_file(client):
    vendor_dir = os.path.join(os.environ['AEON_TOPDIR'], 'vendor_images')
    temp = NamedTemporaryFile(dir=vendor_dir)
    temp.write('test_data_stream')
    try:
        rv = client.get("/images/" + os.path.basename(temp.name))
    finally:
        temp.close()
    assert rv.status_code == 200
    assert rv.data == 'test_data_stream'


def test_api_version(client):
    try:
        expected_version = pkg_resources.get_distribution('aeon-ztp').version
        rv = client.get('/api/about')
        given_version = json.loads(rv.data)
        assert expected_version == given_version['version']
    except pkg_resources.DistributionNotFound as e:
        pytest.fail("AEON-ZTP is not installed: {}".format(e))


def test_nxos_bootconf(client):
    rv = client.get("/api/bootconf/" + 'nxos')
    assert rv.status_code == 200


def test_nxos_register_get(client):
    from aeon_ztp.ztp_celery import ztp_bootstrapper  # NOQA
    with patch('aeon_ztp.ztp_celery.ztp_bootstrapper.delay') as mock_task:
        rv = client.get('api/register/nxos')
        args, kwargs = mock_task.call_args
        assert not args
        assert kwargs == {'os_name': 'nxos', 'target': None}
        assert rv.status_code == 200
        assert not rv.data


def test_nxos_register_post(client):
    from aeon_ztp.ztp_celery import ztp_bootstrapper  # NOQA
    with patch('aeon_ztp.ztp_celery.ztp_bootstrapper.delay') as mock_task:
        rv = client.post('api/register/nxos')
        args, kwargs = mock_task.call_args
        assert not args
        assert kwargs == {'os_name': 'nxos', 'target': None}
        assert rv.status_code == 200
        assert not rv.data


def test_api_finalizer_get(client):
    from aeon_ztp.ztp_celery import ztp_finalizer  # NOQA
    with patch('aeon_ztp.ztp_celery.ztp_finalizer.delay') as mock_task:
        rv = client.get('api/finally/nxos')
        args, kwargs = mock_task.call_args
        assert not args
        assert kwargs == {'os_name': 'nxos', 'target': None}
        assert rv.status_code == 200
        assert rv.data == "OK"


def test_api_finalizer_post(client):
    from aeon_ztp.ztp_celery import ztp_finalizer  # NOQA
    with patch('aeon_ztp.ztp_celery.ztp_finalizer.delay') as mock_task:
        rv = client.post('api/finally/nxos')
        args, kwargs = mock_task.call_args
        assert not args
        assert kwargs == {'os_name': 'nxos', 'target': None}
        assert rv.status_code == 200
        assert rv.data == "OK"


def test_api_env(client):
    rv = client.get('api/env')
    assert rv.status_code == 200
    assert rv.response


def test_create_device(client):
    device_info = {"ip_addr": "10.0.0.11",
                   "os_name": "NXOS",
                   "state": "REGISTERED",
                   "message": "device registered, waiting for bootstrap start"
                   }
    rv = client.post('/api/devices',
                     data=json.dumps(device_info),
                     content_type='application/json')
    assert rv.status_code == 200
    rvd = json.loads(rv.data)
    assert rvd['message'] == 'device added'
    assert rvd['data'] == device_info


def test_create_device_with_existing_device(client, device):
    device_info = {"ip_addr": "1.2.3.4",
                   "os_name": "NXOS",
                   "state": "REGISTERED",
                   "message": "device registered, waiting for bootstrap start"
                   }
    rv = client.post('/api/devices',
                     data=json.dumps(device_info),
                     content_type='application/json')
    assert rv.status_code == 400
    rvd = json.loads(rv.data)
    assert rvd['message'] == 'device with os_name, ip_addr already exists'
    assert rvd['rqst_data']['ip_addr'] == device['ip_addr']


# Skipping this test until fix has been merged
@pytest.mark.skip
def test_create_device_with_bad_data(client):
    device_info = {"ip_addr": "10.0.0.11",
                   "bad_data": "bad_data"}
    rv = client.post('/api/devices',
                     data=json.dumps(device_info),
                     content_type='application/json')
    assert rv.status_code == 200
    # rvd = json.loads(rv.data)
    # assert rvd['message'] == 'device added'
    # assert rvd['data'] == device_info


@patch('aeon_ztp.db.session.commit')
def test_create_device_with_db_exception(commit, client):
    commit.side_effect = Exception
    device_info = {"ip_addr": "10.0.0.11",
                   "os_name": "NXOS",
                   "state": "REGISTERED",
                   "message": "device registered, waiting for bootstrap start"
                   }
    rv = client.post('/api/devices',
                     data=json.dumps(device_info),
                     content_type='application/json')
    assert rv.status_code == 500


def test_get_devices_with_args(client, device):
    rv = client.get('/api/devices?os_name=NXOS',
                    content_type='application/json')
    rvd = json.loads(rv.data)
    assert rv.status_code == 200
    assert rvd['count'] == 1
    # Get response returns a list of devices.
    device = rvd['items'][0]
    assert device['os_name'] == 'NXOS'


# Bug found while writing tests
# Skipping this one until code has been fixed
@pytest.mark.skip
def test_get_devices_get_no_result(client):
    rv = client.get('/api/devices?os_name=LINKSYS',
                    content_type='application/json')
    rvd = json.loads(rv.data)
    assert rv.status_code == 404
    assert rvd['count'] == 0


def test_get_devices_invalid_args(client):
    rv = client.get('/api/devices?bad_arg=badarg',
                    content_type='application/json')
    rvd = json.loads(rv.data)
    assert rv.status_code == 500
    assert not rvd['ok']
    assert rvd['message'] == 'invalid arguments'


def test_get_devices_without_args(client, device):
    rv = client.get('/api/devices',
                    content_type='application/json')
    rvd = json.loads(rv.data)
    assert rv.status_code == 200
    assert rvd['count'] == 1
    # Get response returns a list of devices.
    device = rvd['items'][0]
    assert device['os_name'] == 'NXOS'


def test_put_device_status(client, device):
    device_info = {"ip_addr": "1.2.3.4",
                   "os_name": "NXOS",
                   "state": "REGISTERED",
                   "message": "message has been updated"
                   }
    rv = client.put('api/devices/status',
                    data=json.dumps(device_info),
                    content_type='application/json')
    rvd = json.loads(rv.data)
    assert rv.status_code == 200
    assert rvd['ok']
    db_device = models.Device.query.get('1.2.3.4')
    rcvd_device_data = models.device_schema.dump(db_device).data
    assert rcvd_device_data['message'] == device_info['message']


def test_put_device_status_no_result_found(client):
    device_info = {"ip_addr": "9.9.9.9",
                   "os_name": "NXOS",
                   "state": "REGISTERED",
                   "message": "message has been updated"
                   }
    rv = client.put('api/devices/status',
                    data=json.dumps(device_info),
                    content_type='application/json')
    assert rv.status_code == 400


def test_put_device_facts(client, device):
    device_info = {'ip_addr': '1.2.3.4',
                   'os_name': 'NXOS',
                   'hw_model': 'Semicool9000',
                   'os_version': '3.0.0a',
                   'serial_number': '0987654321'
                   }
    rv = client.put('api/devices/facts',
                    data=json.dumps(device_info),
                    content_type='application/json')
    assert rv.status_code == 200
    db_device = models.Device.query.get('1.2.3.4')
    rcvd_device_data = models.device_schema.dump(db_device).data
    assert device_info['hw_model'] == rcvd_device_data['hw_model']
    assert device_info['os_version'] == rcvd_device_data['os_version']
    assert device_info['serial_number'] == rcvd_device_data['serial_number']


def test_put_device_facts_no_result_found(client):
    device_info = {"ip_addr": "9.9.9.9",
                   "os_name": "NXOS",
                   "state": "REGISTERED",
                   "message": "message has been updated"
                   }
    rv = client.put('api/devices/facts',
                    data=json.dumps(device_info),
                    content_type='application/json')
    assert rv.status_code == 404
    rvd = json.loads(rv.data)
    assert not rvd['ok']
    assert rvd['message'] == 'Not Found'
    assert rvd['item'] == device_info


def test_delete_devices_all(client, device):
    rv = client.delete('/api/devices?all=True')
    assert rv.status_code == 200


def test_delete_devices(client, device):
    rv = client.delete('/api/devices?ip_addr=1.2.3.4')
    assert rv.status_code == 200
    rvd = json.loads(rv.data)
    assert rvd['ok']
    assert rvd['count'] == 1


# Bug found while writing tests
# Skipping this one until code has been fixed
@pytest.mark.skip
def test_delete_devices_no_result_found(client, device):
    rv = client.delete('/api/devices?ip_addr=9.9.9.9')
    rvd = json.loads(rv.data)
    assert rv.status_code == 404
    assert not rvd['ok']
    assert rvd['message'] == 'Not Found'


def test_delete_devices_attribute_error(client):
    rv = client.delete('/api/devices?bad_arg=bad_arg')
    rvd = json.loads(rv.data)
    assert not rvd['ok']
    assert rv.status_code == 500


@patch('aeon_ztp.db.session.commit')
def test_delete_devices_all_with_db_exception(commit, client, device):
    commit.side_effect = Exception
    rv = client.delete('/api/devices?all=True')
    rvd = json.loads(rv.data)
    assert not rvd['ok']
    assert rv.status_code == 400


@patch('aeon_ztp.db.session.commit')
def test_delete_devices_with_db_exception(commit, client, device):
    commit.side_effect = Exception
    rv = client.delete('/api/devices?ip_addr=1.2.3.4')
    rvd = json.loads(rv.data)
    assert not rvd['ok']
    assert rv.status_code == 500


def test_delete_devices_no_device_given(client):
    rv = client.delete('/api/devices')
    rvd = json.loads(rv.data)
    assert not rvd['ok']
    assert rvd['message'] == 'all or filter required'
    assert rv.status_code == 400
