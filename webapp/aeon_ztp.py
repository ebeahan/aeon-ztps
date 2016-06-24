#!/usr/bin/python
from flask import request, send_from_directory

from aeon_ztp_app import app
import ztp_celery
import ztp_api_devices

__all__ = ['app']


@app.route('/downloads/<path:filename>', methods=['GET'])
def download_file(filename):
    return send_from_directory('/opt/aeon-ztp/downloads', filename)


@app.route('/images/<path:filename>', methods=['GET'])
def get_vendor_file(filename):
    return send_from_directory('/opt/aeon-ztp/vendor_images', filename)


@app.route('/api/bootconf/<os_name>')
def nxos_bootconf(os_name):
    return send_from_directory('static', '%s-boot.conf' % os_name)


@app.route('/api/register/<os_name>', methods=['GET', 'POST'])
def nxos_register(os_name):
    from_ipaddr = request.args.get('ipaddr') or request.remote_addr
    ztp_celery.ztp_bootstrapper.delay(os_name=os_name, target=from_ipaddr)
    return ""


@app.route('/test/finalizer/<os_name>', methods=['GET', 'POST'])
def api_finalizer(os_name):
    from_ipaddr = request.args.get('ipaddr') or request.remote_addr
    ztp_celery.ztp_finalizer.delay(os_name=os_name, target=from_ipaddr)
    return "OK"
