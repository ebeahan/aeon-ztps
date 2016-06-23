import subprocess

from celery import Celery

__all__ = ['ztp_bootstrapper']

celery_config = dict()
celery_config['CELERY_BROKER_URL'] = 'amqp://'
celery_config['CELERY_RESULT_BACKEND'] = 'rpc://'

celery = Celery('aeon-ztp', broker=celery_config['CELERY_BROKER_URL'])
celery.conf.update(celery_config)

_AEON_DIR = '/opt/aeon-ztp'


@celery.task
def ztp_bootstrapper(os_name, target_ipaddr):

    cmd_args = [
        '%s/bin/%s-bootstrap' % (_AEON_DIR, os_name),
        '--target %s' % target_ipaddr,
        '--topdir %s' % _AEON_DIR,
        '-U AEON_TUSER',
        '-P AEON_TPASSWD',
        '--logfile /var/log/aeon-ztp/bootstrapper.log'
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

    print "rc={}".format(rc)
    print "stdout={}".format(_stdout)
    print "stderr={}".format(_stderr)
