#!/usr/bin/python
# Copyright 2014-present, Apstra, Inc. All rights reserved.
#
# This source code is licensed under End User License Agreement found in the
# LICENSE file at http://www.apstra.com/community/eula
import aeon_ztp
import pkg_resources
import pytest
from tempfile import NamedTemporaryFile
import os
import json
tests_path = os.path.dirname(os.path.realpath(__file__))
os.environ['AEON_TOPDIR'] = os.path.abspath(os.path.join(tests_path, os.pardir))
from aeon_ztp import create_app
from mock import patch


@pytest.fixture(scope="session")
def app():
    """
    Creates a new Flask session for testing
    """

    _app = create_app('testing')
    app_ctx = _app.app_context()
    app_ctx.push()
    test_client = _app.test_client()
    yield test_client
    # Code after the yield statement becomes teardown
    aeon_ztp.db.session.remove()
    app_ctx.pop()


def test_download_file(app):
    """
    Creates a temporary file and verifies that it can be downloaded
    """
    download_dir = os.path.join(os.environ['AEON_TOPDIR'], 'downloads')
    temp = NamedTemporaryFile(dir=download_dir)
    temp.write('test_data_stream')
    try:
        response = app.get("/downloads/" + os.path.basename(temp.name))
    finally:
        temp.close()
    assert response.status_code == 200
    assert response.data == 'test_data_stream'


def test_get_vendor_file(app):
    vendor_dir = os.path.join(os.environ['AEON_TOPDIR'], 'vendor_images')
    temp = NamedTemporaryFile(dir=vendor_dir)
    temp.write('test_data_stream')
    try:
        response = app.get("/images/" + os.path.basename(temp.name))
    finally:
        temp.close()
    assert response.status_code == 200
    assert response.data == 'test_data_stream'


def test_api_version(app):
    try:
        expected_version = pkg_resources.get_distribution('aeon-ztp').version
        response = app.get('/api/about')
        given_version = json.loads(response.data)
        assert expected_version == given_version['version']
    except pkg_resources.DistributionNotFound as e:
        pytest.fail("AEON-ZTP is not installed: {}".format(e))


def test_nxos_bootconf(app):
    response = app.get("/api/bootconf/" + 'nxos')
    assert response.status_code == 200


def test_nxos_register_get(app):
    from aeon_ztp.ztp_celery import ztp_bootstrapper
    with patch('aeon_ztp.ztp_celery.ztp_bootstrapper.delay') as mock_task:
        response = app.get('api/register/nxos')
        args, kwargs = mock_task.call_args
        assert not args
        assert kwargs == {'os_name': 'nxos', 'target': None}
        assert response.status_code == 200
        assert not response.data


def test_nxos_register_post(app):
    from aeon_ztp.ztp_celery import ztp_bootstrapper
    with patch('aeon_ztp.ztp_celery.ztp_bootstrapper.delay') as mock_task:
        response = app.post('api/register/nxos')
        args, kwargs = mock_task.call_args
        assert not args
        assert kwargs == {'os_name': 'nxos', 'target': None}
        assert response.status_code == 200
        assert not response.data


def test_api_finalizer_get(app):
    from aeon_ztp.ztp_celery import ztp_finalizer
    with patch('aeon_ztp.ztp_celery.ztp_finalizer.delay') as mock_task:
        response = app.get('api/finally/nxos')
        args, kwargs = mock_task.call_args
        assert not args
        assert kwargs == {'os_name': 'nxos', 'target': None}
        assert response.status_code == 200
        assert response.data == "OK"


def test_api_finalizer_post(app):
    from aeon_ztp.ztp_celery import ztp_finalizer
    with patch('aeon_ztp.ztp_celery.ztp_finalizer.delay') as mock_task:
        response = app.post('api/finally/nxos')
        args, kwargs = mock_task.call_args
        assert not args
        assert kwargs == {'os_name': 'nxos', 'target': None}
        assert response.status_code == 200
        assert response.data == "OK"


def test_api_env(app):
    response = app.get('api/env')
    assert response.status_code == 200
    assert response.response