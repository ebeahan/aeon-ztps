import json
import subprocess
import re
import os

from celery import Celery
from ztp_flask import app
import aeon.nxos as nxos

__all__ = ['ztp_bootstrapper']

app.config['CELERY_BROKER_URL'] = 'amqp://'
app.config['CELERY_RESULT_BACKEND'] = 'rpc://'

celery = Celery(app.name, broker=app.config['CELERY_BROKER_URL'])
celery.conf.update(app.config)

# @celery.task
# def bootstrapper(os_name, ip_addr):
#     print "the os is {0} and the ip_addr is {1}".format(os_name, ip_addr)
#     dev = nxos.Device(ip_addr, user='admin', passwd='admin')
#     print json.dumps(dev.facts, indent=4)
#     return 1

@celery.task
def ztp_bootstrapper(os_name, ip_addr):

    cmd_args = [
        'nxos-bootstrap',
        '--target %s' % ip_addr,
        '--server 172.20.80.10',
        '--topdir /home/admin/aeon-ztp/opt',
        '-U AEON_TUSER',
        '-P AEON_TPASSWD',
        '--logfile /home/admin/aztp.log'
    ]

    cmd_str = ' '.join(cmd_args)

    # must pass command as a single string; using shell=True

    this = subprocess.Popen(cmd_str, shell=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    print "starting bootstrapper[pid={pid}] [{cmd_str}]".format(
        pid=this.pid, cmd_str=cmd_str)

    _stdout, _stderr = this.communicate()
    rc = this.returncode

    print "rc={}".format(rc)
    print "stdout={}".format(_stdout)
    print "stderr={}".format(_stderr)
