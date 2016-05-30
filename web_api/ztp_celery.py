import json
import subprocess
import re

from celery import Celery
from ztp_flask import app
import aeon.nxos as nxos

__all__ = ['do_this_thing']

app.config['CELERY_BROKER_URL'] = 'amqp://'
app.config['CELERY_RESULT_BACKEND'] = 'rpc://'

celery = Celery(app.name, broker=app.config['CELERY_BROKER_URL'])
celery.conf.update(app.config)

@celery.task
def do_this_thing(os_name, ip_addr):
    print "the os is {0} and the ip_addr is {1}".format(os_name, ip_addr)
    dev = nxos.Device(ip_addr, user='admin', passwd='admin')
    print json.dumps(dev.facts, indent=4)
    return 1

@celery.task
def do_other_thing(os_name, ip_addr):

    run_args = [
        'nxos-gatherfacts',
        '--target %s' % ip_addr
    ]

    # must pass command as a single string; using shell=True
    PIPE = subprocess.PIPE
    this = subprocess.Popen(
        ' '.join(run_args), shell=True,
        stdout=PIPE, stderr=PIPE)

    _stdout, _stderr = this.communicate()
    rc = this.returncode

    print "rc={}".format(rc)
    print _stdout
