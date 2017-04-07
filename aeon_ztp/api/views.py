#!/usr/bin/python
# Copyright 2014-present, Apstra, Inc. All rights reserved.
#
# This source code is licensed under End User License Agreement found in the
# LICENSE file at http://www.apstra.com/community/eula


import os
from datetime import datetime
from os import path

import aeon_ztp
import pkg_resources

from flask import Blueprint, request, jsonify
from flask import send_from_directory
from sqlalchemy import and_ as SQL_AND
from sqlalchemy.orm.exc import NoResultFound

import models
from aeon_ztp import ztp_celery

api = Blueprint('api', __name__)

_AEON_TOPDIR = os.getenv('AEON_TOPDIR')


@api.route('/downloads/<path:filename>', methods=['GET'])
def download_file(filename):
    from_dir = path.join(_AEON_TOPDIR, 'downloads')
    return send_from_directory(from_dir, filename)


@api.route('/images/<path:filename>', methods=['GET'])
def get_vendor_file(filename):
    from_dir = path.join(_AEON_TOPDIR, 'vendor_images')
    return send_from_directory(from_dir, filename)


@api.route('/api/about')
def api_version():
    version = pkg_resources.get_distribution("aeon_ztp").version
    return jsonify(version=version)


@api.route('/api/bootconf/<os_name>')
def nxos_bootconf(os_name):
    from_dir = path.join(_AEON_TOPDIR, 'etc', 'configs', os_name)
    return send_from_directory(from_dir, '%s-boot.conf' % os_name)


@api.route('/api/register/<os_name>', methods=['GET', 'POST'])
def nxos_register(os_name):
    from_ipaddr = request.args.get('ipaddr') or request.remote_addr
    ztp_celery.ztp_bootstrapper.delay(os_name=os_name, target=from_ipaddr)
    return ""


@api.route('/api/finally/<os_name>', methods=['GET', 'POST'])
def api_finalizer(os_name):
    from_ipaddr = request.args.get('ipaddr') or request.remote_addr
    ztp_celery.ztp_finalizer.delay(os_name=os_name, target=from_ipaddr)
    return "OK"


@api.route('/api/env')
def api_env():
    my_env = os.environ.copy()
    return jsonify(my_env)

# -----------------------------------------------------------------------------
#
#                                 Utility Functions
#
# -----------------------------------------------------------------------------


def find_device(db, table, dev_data):
    return db.query(table).filter(SQL_AND(
        table.os_name == dev_data['os_name'],
        table.ip_addr == dev_data['ip_addr']))


def find_devices(db, table, matching):
    """
    :param db: database
    :param table: table
    :param matching: dictionary of column name:value parings
    :return: filtered query items
    """

    filter_list = []
    for name, value in matching.iteritems():
        col = getattr(table, name)
        filter_list.append(col.op('==')(value))

    return db.query(table).filter(SQL_AND(*filter_list))


def time_now():
    now = datetime.now()
    return datetime.isoformat(now)


# -----------------------------------------------------------------------------
# #############################################################################
#
#                                 API ROUTES
#
# #############################################################################
# -----------------------------------------------------------------------------

# -----------------------------------------------------------------------------
#                                 GET /api/devices
# -----------------------------------------------------------------------------

@api.route('/api/devices', methods=['GET'])
def _get_devices():
    db = aeon_ztp.db.session
    to_json = models.device_schema

    # ---------------------------------------------------------------
    # if the request has arguments, use these to form an "and" filter
    # and return only the subset of items matching
    # ---------------------------------------------------------------

    if request.args:
        try:
            recs = find_devices(db, models.Device, request.args)
            if recs.count() == 0:
                return jsonify(ok=False,
                               message='Not Found: %s' % request.query_string), 404

            items = [to_json.dump(rec).data for rec in recs]
            return jsonify(count=len(items), items=items)

        except AttributeError:
            return jsonify(ok=False, message='invalid arguments'), 500

    # -------------------------------------------
    # otherwise, return all items in the database
    # -------------------------------------------

    items = [to_json.dump(rec).data for rec in db.query(models.Device).all()]
    return jsonify(count=len(items), items=items)


# -----------------------------------------------------------------------------
#                                 POST /api/devices
# -----------------------------------------------------------------------------

@api.route('/api/devices', methods=['POST'])
def _create_device():
    device_data = request.get_json()

    db = aeon_ztp.db.session
    table = models.Device

    if not ('os_name' in device_data and 'ip_addr' in device_data):
        return jsonify(
            ok=False, message="Error: rqst-body missing os_name, ip_addr values",
            rqst_data=device_data), 400

    # ----------------------------------------------------------
    # check to see if the device already exists
    # ----------------------------------------------------------

    try:
        rec = find_device(db, table, device_data).one()
        rec.updated_at = time_now()
        rec.message = 'device with os_name, ip_addr already exists'
        db.commit()

        return jsonify(
            ok=True, message='device already exists',
            data=device_data)

    except NoResultFound:
        pass

    # ---------------------------------------------
    # now try to add the new device to the database
    # ---------------------------------------------

    try:
        db.add(table(created_at=time_now(),
                     updated_at=time_now(),
                     **device_data))
        db.commit()

    except Exception as exc:
        return jsonify(
            ok=False,
            error_type=str(type(exc)),
            message=exc.message,
            rqst_data=device_data), 500

    return jsonify(
        ok=True, message='device added',
        data=device_data)


# -----------------------------------------------------------------------------
#                  PUT: /api/devices/status
# -----------------------------------------------------------------------------

@api.route('/api/devices/status', methods=['PUT'])
def _put_device_status():
    rqst_data = request.get_json()

    db = aeon_ztp.db.session
    table = models.Device

    try:
        rec = find_device(db, table, rqst_data).one()

        if rqst_data['state']:
            rec.state = rqst_data['state']

        rec.message = rqst_data.get('message')
        rec.updated_at = time_now()
        db.commit()

    except NoResultFound:
        return jsonify(
            ok=False, message='Not Found',
            item=rqst_data), 400

    return jsonify(ok=True)

# -----------------------------------------------------------------------------
#                  PUT: /api/devices/facts
# -----------------------------------------------------------------------------


@api.route('/api/devices/facts', methods=['PUT'])
def _put_device_facts():
    rqst_data = request.get_json()

    db = aeon_ztp.db.session
    table = models.Device

    try:
        rec = find_device(db, table, rqst_data).one()
        rec.serial_number = rqst_data.get('serial_number')
        rec.hw_model = rqst_data.get('hw_model')
        rec.os_version = rqst_data.get('os_version')
        rec.facts = rqst_data.get('facts')
        rec.updated_at = time_now()
        rec.image_name = rqst_data.get('image_name')
        rec.finally_script = rqst_data.get('finally_script')

        db.commit()

    except NoResultFound:
        return jsonify(
            ok=False, message='Not Found',
            item=rqst_data), 404

    return jsonify(ok=True)


# -----------------------------------------------------------------------------
#                  DELETE: /api/devices
# -----------------------------------------------------------------------------

@api.route('/api/devices', methods=['DELETE'])
def _delete_devices():

    if request.args.get('all'):
        try:
            db = aeon_ztp.db.session
            db.query(models.Device).delete()
            db.commit()

        except Exception as exc:
            return jsonify(
                ok=False,
                message='unable to delete all records: {}'.format(exc.message)), 400

        return jsonify(ok=True, message='all records deleted')

    elif request.args:
        db = aeon_ztp.db.session

        try:
            recs = find_devices(db, models.Device, request.args)
            n_recs = recs.count()
            if n_recs == 0:
                return jsonify(ok=False,
                               message='Not Found: %s' % request.query_string), 404

            recs.delete(synchronize_session=False)
            db.commit()
            return jsonify(
                ok=True, count=n_recs,
                message='{} records deleted'.format(n_recs))

        except AttributeError:
            return jsonify(ok=False, message='invalid arguments'), 500

        except Exception as exc:
            msg = 'unable to delete specific records: {}'.format(exc.message)
            return jsonify(ok=False, message=msg), 500
    else:
        return jsonify(ok=False, message='all or filter required'), 400
