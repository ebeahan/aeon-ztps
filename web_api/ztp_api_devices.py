from flask import request, jsonify
from sqlalchemy import and_ as SQL_AND
from sqlalchemy.orm.exc import NoResultFound

from ztp_flask import app
import ztp_db


@app.route('/api/devices', methods=['HEAD'])
def _get_device_count(dev_sn):
    return "get_device_count {}: OK".format(dev_sn)


@app.route('/api/devices', methods=['GET'])
def _get_all_devices():
    db = ztp_db.get_session()
    to_json = ztp_db.Device.Schema()

    return jsonify(
        items=[to_json.dump(rec).data
               for rec in db.query(ztp_db.Device).all()])


def find_device(db, table, dev_data):
    return db.query(table).filter(SQL_AND(
        table.os_name == dev_data['os_name'],
        table.ip_addr == dev_data['ip_addr']))


@app.route('/api/devices', methods=['POST'])
def _create_device():
    device_data = request.get_json()

    db = ztp_db.get_session()
    table = ztp_db.Device

    # first check to see if there is an existing record that matches the
    # ip_addr/os_name.  if so, then delete it, because we are starting over

    try:
        db.delete(find_device(db, table, device_data).one())
        db.commit()

    except NoResultFound:
        pass

    # now try to add the new device to the database

    try:
        db.add(table(**device_data))
        db.commit()

    except Exception as exc:
        return jsonify(
            ok=False,
            error_type=str(type(exc)),
#            message=exc.message,
            **device_data), 500

    return jsonify(ok=True, **device_data)


# @app.route('/api/devices/<os_name>/<serial_number>', methods=['GET'])
# def _get_device(os_name, serial_number):
#
#     db = ztp_db.get_session()
#     table = ztp_db.Device
#
#     q_rsp = find_device(db, table,
#                         os_name=os_name, serial_number=serial_number)
#
#     try:
#         rec = q_rsp.one()
#     except:
#         return jsonify(
#             ok=False,
#             message='Not Found',
#             item=dict(os_name=os_name, serial_number=serial_number)), 400
#
#     as_dict = ztp_db.Device.Schema()
#     return jsonify(as_dict.dump(rec).data)


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
        db.commit()

    except NoResultFound:
        return jsonify(
            ok=False,
            message='Not Found',
            item=rqst_data), 400

    return jsonify(ok=True)
