from flask import request, jsonify
from ztp_flask import app
import ztp_db

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


@app.route('/api/devices/<dev_sn>', methods=['GET'])
def _get_device(dev_sn):
    return "get_device {}: OK".format(dev_sn)


@app.route('/api/devices/<dev_sn>', methods=['HEAD'])
def _get_device_count(dev_sn):
    return "get_device_count {}: OK".format(dev_sn)


@app.route('/api/devices/<dev_sn>/status', methods=['PUT'])
def _put_device_status(dev_sn):
    return "put_device_status {}: OK".format(dev_sn)
