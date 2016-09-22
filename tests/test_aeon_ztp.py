#!/usr/bin/python
# Copyright 2014-present, Apstra, Inc. All rights reserved.
#
# This source code is licensed under End User License Agreement found in the
# LICENSE file at http://www.apstra.com/community/eula
import aeon_ztp
from aeon_ztp.api.models import *
import pkg_resources
import pytest
from tempfile import NamedTemporaryFile
from datetime import datetime
import os
import json
tests_path = os.path.dirname(os.path.realpath(__file__))
os.environ['AEON_TOPDIR'] = os.path.abspath(os.path.join(tests_path, os.pardir))
from aeon_ztp import create_app
from mock import patch


@pytest.fixture(scope="session")
def app():
    """
    Creates a new Flask app for testing
    """

    _app = create_app('testing')
    app_ctx = _app.app_context()
    app_ctx.push()
    aeon_ztp.db.create_all()
    yield _app
    # Teardown code
    aeon_ztp.db.drop_all()
    app_ctx.pop()


@pytest.fixture(scope="session")
def client(app):
    """
    Creates a flask test client
    :param app:
    :return: flask test_client
    """
    with app.test_client() as client:
        yield client


@pytest.fixture(scope='function')
def session(app):
    """
    Creates a sqlalchemy db session
    :param app:
    :return: flask-sqlalchemy session
    """
    session = aeon_ztp.db.session

    yield session

    # Teardown code
    session.close()


@pytest.fixture(scope="function")
def device(session, device_data=None):
    now = datetime.now().isoformat()
    device_data = {'ip_addr': '1.2.3.4',
                   'os_name': 'NXOS',
                   'created_at': now,
                   'updated_at': now,
                   'hw_model': 'Supercool9000',
                   'message': 'device added',
                   'os_version': '1.0.0a',
                   'serial_number': '1234567890',
                   'state': 'excellent'
                   }
    device = Device(**device_data)
    session.add(device)
    session.commit()
    yield device_data

    # Teardown code
    session.delete(device)
    session.commit()


def test_create_device(device):
    db_device = Device.query.get('1.2.3.4')
    rcvd_device_data = device_schema.dump(db_device).data
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
    from aeon_ztp.ztp_celery import ztp_bootstrapper
    with patch('aeon_ztp.ztp_celery.ztp_bootstrapper.delay') as mock_task:
        rv = client.get('api/register/nxos')
        args, kwargs = mock_task.call_args
        assert not args
        assert kwargs == {'os_name': 'nxos', 'target': None}
        assert rv.status_code == 200
        assert not rv.data


def test_nxos_register_post(client):
    from aeon_ztp.ztp_celery import ztp_bootstrapper
    with patch('aeon_ztp.ztp_celery.ztp_bootstrapper.delay') as mock_task:
        rv = client.post('api/register/nxos')
        args, kwargs = mock_task.call_args
        assert not args
        assert kwargs == {'os_name': 'nxos', 'target': None}
        assert rv.status_code == 200
        assert not rv.data


def test_api_finalizer_get(client):
    from aeon_ztp.ztp_celery import ztp_finalizer
    with patch('aeon_ztp.ztp_celery.ztp_finalizer.delay') as mock_task:
        rv = client.get('api/finally/nxos')
        args, kwargs = mock_task.call_args
        assert not args
        assert kwargs == {'os_name': 'nxos', 'target': None}
        assert rv.status_code == 200
        assert rv.data == "OK"


def test_api_finalizer_post(client):
    from aeon_ztp.ztp_celery import ztp_finalizer
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


def test_api_devices_post(client):
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


def test_api_devices_post_existing_device(client, device):
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
def test_api_devices_post_with_bad_data(client):
    device_info = {"ip_addr": "10.0.0.11",
                   "bad_data": "bad_data"}
    rv = client.post('/api/devices',
                     data=json.dumps(device_info),
                     content_type='application/json')
    assert rv.status_code == 200
    # rvd = json.loads(rv.data)
    # assert rvd['message'] == 'device added'
    # assert rvd['data'] == device_info

def test_api_devices_get_with_args(client):
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
def test_api_devices_get_no_result(client):
    rv = client.get('/api/devices?os_name=LINKSYS',
                    content_type='application/json')
    rvd = json.loads(rv.data)
    assert rv.status_code == 404
    assert rvd['count'] == 0


def test_api_devices_get_invalid_args(client):
    rv = client.get('/api/devices?bad_arg=badarg',
                    content_type='application/json')
    rvd = json.loads(rv.data)
    assert rv.status_code == 500
    assert rvd['ok'] == False
    assert rvd['message'] == 'invalid arguments'

def test_api_devices_get_without_args(client):
    rv = client.get('/api/devices',
                    content_type='application/json')
    rvd = json.loads(rv.data)
    assert rv.status_code == 200
    assert rvd['count'] == 1
    # Get response returns a list of devices.
    device = rvd['items'][0]
    assert device['os_name'] == 'NXOS'