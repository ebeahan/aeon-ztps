# Copyright 2014-present, Apstra, Inc. All rights reserved.
#
# This source code is licensed under End User License Agreement found in the
# LICENSE file at http://www.apstra.com/community/eula

import subprocess
import logging
import os
import socket
import requests

from celery import Celery

__all__ = ['ztp_bootstrapper', 'aos_import']

celery_config = dict()
celery_config['CELERY_BROKER_URL'] = 'amqp://'
celery_config['CELERY_RESULT_BACKEND'] = 'rpc://'

celery = Celery('aeon-ztp', broker=celery_config['CELERY_BROKER_URL'])
celery.conf.update(celery_config)

_AEON_PORT = os.getenv('AEON_HTTP_PORT')
_AEON_DIR = os.getenv('AEON_TOPDIR')
_AEON_LOGFILE = os.getenv('AEON_LOGFILE')


def get_server_ipaddr(dst):
    dst_s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    dst_s.connect((dst, 0))
    return dst_s.getsockname()[0]


def post_device_status(server, target, os_name, message=None, state=None):
    requests.put(
        url='http://%s/api/devices/status' % server,
        json=dict(
            os_name=os_name, ip_addr=target,
            state=state, message=message))


def setup_logging(logname, logfile, target):
    log = logging.getLogger(name=logname)
    log.setLevel(logging.INFO)
    fh = logging.FileHandler(logfile)
    fmt = logging.Formatter(
        '%(asctime)s:%(levelname)s:{target}:%(message)s'.format(target=target))
    fh.setFormatter(fmt)
    log.addHandler(fh)
    return log


def do_finalize(server, os_name, target, log):
    profile_dir = os.path.join(_AEON_DIR, 'etc', 'profiles', 'default', os_name)
    finalizer = os.path.join(profile_dir, 'finally')

    if not os.path.isfile(finalizer):
        log.info('no user provided finally script')
        return 0

    cmd = '{prog}'.format(prog=finalizer)

    this_env = os.environ.copy()
    this_env.update(dict(
        AEON_LOGFILE=_AEON_LOGFILE,
        AEON_TARGET=target,
        AEON_SERVER=server))

    message = "executing 'finally' script: {cmd}".format(cmd=cmd)
    log.info(message)
    post_device_status(server=server,
                       os_name=os_name, target=target,
                       state='FINALLY', message=message)

    child = subprocess.Popen(
        cmd, shell=True, env=this_env,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    _stdout, _stderr = child.communicate()
    rc = child.returncode

    log.info("finally rc={} stdout=[{}]".format(rc, _stdout))
    if len(_stderr):
        log.info("finally stderr=[{}]".format(_stderr))

    return rc


def do_bootstrapper(server, os_name, target, log):
    prog = '%s/bin/%s-bootstrap' % (_AEON_DIR, os_name)

    cmd_args = [
        prog,
        '--target %s' % target,
        '--server %s' % server,
        '--topdir %s' % _AEON_DIR,
        '-U AEON_TUSER',
        '-P AEON_TPASSWD',
        '--logfile %s' % _AEON_LOGFILE
    ]

    cmd_str = ' '.join(cmd_args)

    # must pass command as a single string; using shell=True

    this = subprocess.Popen(
        cmd_str, shell=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    log.info("starting bootstrapper[pid={pid}] [{cmd_str}]".format(
        pid=this.pid, cmd_str=cmd_str))

    _stdout, _stderr = this.communicate()
    rc = this.returncode

    log.info("rc={} stdout={}".format(rc, _stdout))
    if len(_stderr):
        log.error("stderr={}".format(_stderr))

    return rc


@celery.task
def ztp_bootstrapper(os_name, target):

    server = "{}:{}".format(get_server_ipaddr(target), _AEON_PORT)

    log = setup_logging(
        logname='aeon-bootstrapper', logfile=_AEON_LOGFILE,
        target=target)

    got = requests.post(
        url='http://%s/api/devices' % server,
        json=dict(
            ip_addr=target, os_name=os_name,
            state='REGISTERED',
            message='device registered, waiting for bootstrap start'))

    if not got.ok:
        body = got.json()
        log.error('Unable to register device: %s' % body['message'])
        return got.status_code

    rc = do_bootstrapper(server=server, os_name=os_name, target=target, log=log)
    if 0 != rc:
        return rc

    rc = do_finalize(server=server, os_name=os_name, target=target, log=log)
    if 0 != rc:
        return rc

    post_device_status(server=server,
                       os_name=os_name, target=target,
                       state='DONE', message='device bootstrap completed')

    return rc


@celery.task
def ztp_finalizer(os_name, target):
    server = "{}:{}".format(get_server_ipaddr(target), _AEON_PORT)

    log = setup_logging(
        logname='aeon-finalizer', logfile=_AEON_LOGFILE,
        target=target)

    return do_finalize(os_name=os_name, target=target, server=server, log=log)


@celery.task
def aos_import(ip_address):
    print ip_address
    try:
        aos_import = subprocess.check_output(['aosetc-import', ip_address])
        return aos_import
    except subprocess.CalledProcessError as e:
        return e.output
    # for stdout_line in iter(aos_import.stdout.readline, ""):
    #     yield stdout_line