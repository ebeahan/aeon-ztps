#!/usr/bin/python
# Copyright 2014-present, Apstra, Inc. All rights reserved.
#
# This source code is licensed under End User License Agreement found in the
# LICENSE file at http://www.apstra.com/community/eula

import pkg_resources
import pytest
from tempfile import mkstemp
from tempfile import NamedTemporaryFile
import os
tests_path = os.path.dirname(os.path.realpath(__file__))
os.environ['AEON_TOPDIR'] = os.path.abspath(os.path.join(tests_path, os.pardir))
from webapp import aeon_ztp
from mock import patch


@pytest.fixture(scope="session")
def app(request):
    """
    Creates a new Flask session for testing
    """
    db_fd, aeon_ztp.app.config['DATABASE'] = mkstemp()
    _app = aeon_ztp.app.test_client()

    def teardown():
        os.close(db_fd)
        os.unlink(aeon_ztp.app.config['DATABASE'])
    request.addfinalizer(teardown)
    return _app


def test_download_file(app):
    """
    Creates a temporary file and verfies that it can be downloaded
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


@pytest.mark.skip(reason="We need to figure out versioning")
def test_api_version(app):
    try:
        version = pkg_resources.require("aeon-ztp")[0].version
        response = app.get('/api/about')
        assert response == version
    except pkg_resources.DistributionNotFound as e:
        pytest.fail("AEON-ZTP is not installed: {}".format(e))


def test_nxos_bootconf(app):
    response = app.get("/api/bootconf/" + 'nxos')
    assert response.status_code == 200


def test_nxos_register_get(app):
    from webapp.ztp_celery import ztp_bootstrapper
    with patch('webapp.ztp_celery.ztp_bootstrapper.delay') as mock_task:
        response = app.get('api/register/nxos')
        args, kwargs = mock_task.call_args
        assert not args
        assert kwargs == {'os_name': 'nxos', 'target': None}
        assert response.status_code == 200
        assert not response.data


def test_nxos_register_post(app):
    from webapp.ztp_celery import ztp_bootstrapper
    with patch('webapp.ztp_celery.ztp_bootstrapper.delay') as mock_task:
        response = app.post('api/register/nxos')
        args, kwargs = mock_task.call_args
        assert not args
        assert kwargs == {'os_name': 'nxos', 'target': None}
        assert response.status_code == 200
        assert not response.data


def test_api_finalizer_get(app):
    from webapp.ztp_celery import ztp_finalizer
    with patch('webapp.ztp_celery.ztp_finalizer.delay') as mock_task:
        response = app.get('api/finally/nxos')
        args, kwargs = mock_task.call_args
        assert not args
        assert kwargs == {'os_name': 'nxos', 'target': None}
        assert response.status_code == 200
        assert response.data == "OK"


def test_api_finalizer_post(app):
    from webapp.ztp_celery import ztp_finalizer
    with patch('webapp.ztp_celery.ztp_finalizer.delay') as mock_task:
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