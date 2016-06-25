import subprocess
import logging
import os
import socket
import requests

from celery import Celery

__all__ = ['ztp_bootstrapper']

celery_config = dict()
celery_config['CELERY_BROKER_URL'] = 'amqp://'
celery_config['CELERY_RESULT_BACKEND'] = 'rpc://'

celery = Celery('aeon-ztp', broker=celery_config['CELERY_BROKER_URL'])
celery.conf.update(celery_config)

_AEON_PORT = 8080
_AEON_DIR = '/opt/aeon-ztp'
_AEON_LOGFILE = '/var/log/aeon-ztp/bootstrapper.log'


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


def get_server_ipaddr(dst):
    dst_s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    dst_s.connect((dst, 0))
    return dst_s.getsockname()[0]


def do_finalize(os_name, target):
    my_server_ipaddr = get_server_ipaddr(target)
    profile_dir = os.path.join(_AEON_DIR, 'etc', 'profiles', 'default', os_name)
    finalizer = os.path.join(profile_dir, 'finally')

    log = setup_logging(
        logname='finalizer', logfile=_AEON_LOGFILE,
        target=target)

    if not os.path.isfile(finalizer):
        log.info('no user provided finally script')
        return 0

    cmd = '{prog}'.format(prog=finalizer)

    this_env = os.environ.copy()
    this_env.update(dict(
        AEON_LOGFILE=_AEON_LOGFILE,
        AEON_TARGET=target,
        AEON_SERVER='%s:%s' % (my_server_ipaddr, _AEON_PORT)))

    message = "executing 'finally' script: {cmd}".format(cmd=cmd)
    log.info(message)
    post_device_status(server=my_server_ipaddr,
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


def do_bootstrapper(os_name, target):
    prog = '%s/bin/%s-bootstrap' % (_AEON_DIR, os_name)

    cmd_args = [
        prog,
        '--target %s' % target,
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

    print "starting bootstrapper[pid={pid}] [{cmd_str}]".format(
        pid=this.pid, cmd_str=cmd_str)

    _stdout, _stderr = this.communicate()
    rc = this.returncode

    print "rc={} stdout={}".format(rc, _stdout)
    if len(_stderr):
        print "stderr={}".format(_stderr)

    return rc

@celery.task
def ztp_bootstrapper(os_name, target):

    rc = do_bootstrapper(os_name=os_name, target=target)
    if 0 != rc:
        return rc

    rc = do_finalize(os_name=os_name, target=target)
    return rc


@celery.task
def ztp_finalizer(os_name, target):
    rc = do_finalize(os_name=os_name, target=target)
    return rc
