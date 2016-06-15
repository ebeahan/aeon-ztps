import subprocess

from celery import Celery
from aeon-ztp import app

__all__ = ['ztp_bootstrapper']

app.config['CELERY_BROKER_URL'] = 'amqp://'
app.config['CELERY_RESULT_BACKEND'] = 'rpc://'

celery = Celery(app.name, broker=app.config['CELERY_BROKER_URL'])
celery.conf.update(app.config)


@celery.task
def ztp_bootstrapper(os_name, target_ipaddr):

    cmd_args = [
        'nxos-bootstrap',
        '--target %s' % target_ipaddr,
        '--topdir /opt/aeon-ztp',
        '-U AEON_TUSER',
        '-P AEON_TPASSWD',
        '--logfile /var/log/aeon-ztp/bootstrapper.log'
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
