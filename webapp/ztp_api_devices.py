from datetime import datetime
from flask import request, jsonify
from sqlalchemy import and_ as SQL_AND
from sqlalchemy.orm.exc import NoResultFound

from aeon_ztp_app import app
import ztp_db


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

@app.route('/api/devices', methods=['GET'])
def _get_devices():
    db = ztp_db.get_session()
    to_json = ztp_db.Device.Schema()

    # ---------------------------------------------------------------
    # if the request has arguments, use these to form an "and" filter
    # and return only the subset of items matching
    # ---------------------------------------------------------------

    if request.args:
        try:
            recs = find_devices(db, ztp_db.Device, request.args)
            items = [to_json.dump(rec).data for rec in recs]
            return jsonify(count=len(items), items=items)

        except NoResultFound:
            return jsonify(ok=False, message='Not Found'), 404

        except AttributeError:
            return jsonify(ok=False, message='invalid arguments'), 500

    # -------------------------------------------
    # otherwise, return all items in the database
    # -------------------------------------------

    items = [to_json.dump(rec).data for rec in db.query(ztp_db.Device).all()]
    return jsonify(count=len(items), items=items)


# -----------------------------------------------------------------------------
#                                 POST /api/devices
# -----------------------------------------------------------------------------

@app.route('/api/devices', methods=['POST'])
def _create_device():
    device_data = request.get_json()

    db = ztp_db.get_session()
    table = ztp_db.Device

    # ----------------------------------------------------------
    # check to see if the device already exists, and if it does,
    # then reject the request
    # ----------------------------------------------------------

    try:
        rec = find_device(db, table, device_data).one()
        rec.state = 'ERROR'
        rec.updated_at = time_now()
        rec.message = 'device with os_name, ip_addr already exists'
        db.commit()

        return jsonify(
            ok=False, message=rec.message,
            rqst_data=device_data), 400

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

@app.route('/api/devices/status', methods=['PUT'])
def _put_device_status():
    rqst_data = request.get_json()

    db = ztp_db.get_session()
    table = ztp_db.Device

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


@app.route('/api/devices/facts', methods=['PUT'])
def _put_device_facts():
    rqst_data = request.get_json()

    db = ztp_db.get_session()
    table = ztp_db.Device

    try:
        rec = find_device(db, table, rqst_data).one()
        rec.ip_addr = rqst_data.get('ip_addr')
        rec.os_name = rqst_data.get('os_name')
        rec.serial_number = rqst_data.get('serial_number')
        rec.hw_model = rqst_data.get('hw_model')
        rec.os_version = rqst_data.get('os_version')
        rec.updated_at = time_now()
        db.commit()

    except NoResultFound:
        return jsonify(
            ok=False, message='Not Found',
            item=rqst_data), 404

    return jsonify(ok=True)


# -----------------------------------------------------------------------------
#                  DELETE: /api/devices
# -----------------------------------------------------------------------------

@app.route('/api/devices', methods=['DELETE'])
def _delete_devices():

    arg_all = request.args.get('all')
    if not arg_all:
        return jsonify(
            ok=False, message='all must be true for now'), 400

    try:
        db = ztp_db.get_session()
        db.query(ztp_db.Device).delete()
        db.commit()

    except Exception as exc:
        return jsonify(
            ok=False,
            message='unable to delete all records: {}'.format(exc.message)), 400

    return jsonify(ok=True, message='all records deleted')
