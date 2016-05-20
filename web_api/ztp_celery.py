import json

from celery import Celery
from ztp_flask import app
from aeon.nxos import NxosDevice

__all__ = ['do_this_thing']

app.config['CELERY_BROKER_URL'] = 'amqp://'
app.config['CELERY_RESULT_BACKEND'] = 'rpc://'

print "--> {}".format(app.name)

celery = Celery(app.name, broker=app.config['CELERY_BROKER_URL'])
celery.conf.update(app.config)

@celery.task
def do_this_thing(os_name, ip_addr):
    print "the os is {0} and the ip_addr is {1}".format(os_name, ip_addr)
    dev = NxosDevice(ip_addr, user='admin', passwd='admin')
    print json.dumps(dev.facts, indent=4)
    return 1
