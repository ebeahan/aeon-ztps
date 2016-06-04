from flask import request, jsonify
from sqlalchemy import and_ as SQL_AND

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


@app.route('/api/devices', methods=['POST'])
def _create_device():
    device_data = request.get_json()

    try:
        session = ztp_db.get_session()
        new_rec = ztp_db.Device(**device_data)
        session.merge(new_rec)
        session.commit()

    except Exception as exc:
        return jsonify(
            ok=False,
            error_type=str(type(exc)),
            message=exc.message,
            **device_data), 500

    return jsonify(
        ok=True,
        serial_number=device_data['serial_number'])


def find_device(db, table, os_name, serial_number):
    return db.query(table).filter(SQL_AND(
        table.os_name == os_name,
        table.serial_number == serial_number))


@app.route('/api/devices/<os_name>/<serial_number>', methods=['GET'])
def _get_device(os_name, serial_number):

    db = ztp_db.get_session()
    table = ztp_db.Device

    q_rsp = find_device(db, table,
                        os_name=os_name, serial_number=serial_number)

    try:
        rec = q_rsp.one()
    except:
        return jsonify(
            ok=False,
            message='Not Found',
            item=dict(os_name=os_name, serial_number=serial_number)), 400

    as_dict = ztp_db.Device.Schema()
    return jsonify(as_dict.dump(rec).data)


@app.route('/api/devices/status', methods=['PUT'])
def _put_device_status():
    rqst_data = request.get_json()

    db = ztp_db.get_session()
    table = ztp_db.Device

    q_rsp = find_device(db, table,
                        rqst_data['os_name'], rqst_data['serial_number'])

    rec = q_rsp.one()
    if not rec:
        return jsonify(
            ok=False,
            message='Not Found',
            item=rqst_data), 400

    rec.state = rqst_data['state']
    rec.message = rqst_data.get('message')
    db.commit()

    return jsonify(ok=True)
