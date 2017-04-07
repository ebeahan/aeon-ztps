#!/usr/bin/python
# Copyright 2014-present, Apstra, Inc. All rights reserved.
#
# This source code is licensed under End User License Agreement found in the
# LICENSE file at http://www.apstra.com/community/eula
import os
import aeon_ztp
import aeon_ztp.api.models as models
import pytest
from aeon_ztp import create_app
from datetime import datetime
from sqlalchemy.orm.exc import ObjectDeletedError

tests_path = os.path.dirname(os.path.realpath(__file__))
os.environ['AEON_TOPDIR'] = os.path.abspath(os.path.join(tests_path, os.pardir))


@pytest.fixture()
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


@pytest.fixture()
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
                   'state': 'excellent',
                   'finally_script': 'finally',
                   'image_name': '1.0.1b',
                   'facts': '{"mac_address": "00112233445566"}'
                   }
    device = models.Device(**device_data)
    session.add(device)
    session.commit()
    yield device_data

    # Teardown code
    try:
        session.delete(device)
        session.commit()
    except ObjectDeletedError:
        pass
