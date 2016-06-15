#!/usr/bin/python
from flask import request, send_from_directory

from aeon_ztp_app import app
import ztp_celery
import ztp_api_devices

__all__ = ['app']


@app.route('/api/downloads/<path:filename>', methods=['GET'])
def static_file(filename):
    return send_from_directory('downloads', filename)


@app.route('/api/config0/nxos')
def nxos_bootconf():
    return send_from_directory('static', 'nxos-config0.conf')


@app.route('/api/register/<os_name>', methods=['GET', 'POST'])
def nxos_register(os_name):
    from_ipaddr = request.args.get('ipaddr') or request.remote_addr
    ztp_celery.ztp_bootstrapper.delay(os_name=os_name, target_ipaddr=from_ipaddr)
    return ""

