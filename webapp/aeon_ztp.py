#!/usr/bin/python

import os
from os import path
from flask import request, send_from_directory, jsonify

from aeon_ztp_app import app
import ztp_celery
import ztp_api_devices

__all__ = ['app']

_AEON_TOPDIR = '/opt/aeon-ztp'


@app.route('/downloads/<path:filename>', methods=['GET'])
def download_file(filename):
    from_dir = path.join(_AEON_TOPDIR, 'downloads')
    return send_from_directory(from_dir, filename)


@app.route('/images/<path:filename>', methods=['GET'])
def get_vendor_file(filename):
    from_dir = path.join(_AEON_TOPDIR, 'vendor_images')
    return send_from_directory(from_dir, filename)


@app.route('/api/bootconf/<os_name>')
def nxos_bootconf(os_name):
    from_dir = path.join(_AEON_TOPDIR, 'etc', 'configs', os_name)
    return send_from_directory(from_dir, '%s-boot.conf' % os_name)


@app.route('/api/register/<os_name>', methods=['GET', 'POST'])
def nxos_register(os_name):
    from_ipaddr = request.args.get('ipaddr') or request.remote_addr
    ztp_celery.ztp_bootstrapper.delay(os_name=os_name, target=from_ipaddr)
    return ""


@app.route('/api/finally/<os_name>', methods=['GET', 'POST'])
def api_finalizer(os_name):
    from_ipaddr = request.args.get('ipaddr') or request.remote_addr
    ztp_celery.ztp_finalizer.delay(os_name=os_name, target=from_ipaddr)
    return "OK"


@app.route('/api/env')
def api_env():
    return jsonify(dict(AEON_TOPDIR=_AEON_TOPDIR))
