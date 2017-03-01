#!/usr/bin/env python

# nxos-bootstrap

import sys
import os
import json
import argparse
import subprocess
import logging
import time
import requests
from retrying import retry

import aeon.nxos as nxos
import aeon.nxos.exceptions as NxExc
from aeon.exceptions import ProbeError, UnauthorizedError

_OS_NAME = 'nxos'
_PROGNAME = '%s-bootstrap' % _OS_NAME
_PROGVER = '0.0.1'


# ##### -----------------------------------------------------------------------
# #####
# #####                           Command Line Arguments
# #####
# ##### -----------------------------------------------------------------------

psr = argparse.ArgumentParser(
    prog=_PROGNAME,
    description="Aeon ZTP bootstrapper for Arista EOS",
    add_help=True)

psr.add_argument(
    '--target', required=True,
    help='hostname or ip_addr of target device')

psr.add_argument(
    '--server', required=True,
    help='Aeon ZTP server host:port')

psr.add_argument(
    '--topdir', required=True,
    help='Aeon ZTP server installation directory')

psr.add_argument(
    '--logfile',
    help='name of log file')

psr.add_argument(
    '--reload-delay',
    dest='reload_delay',
    type=int, default=10 * 60,
    help="about of time/s to try to reconnect to device after reload")

psr.add_argument(
    '--init-delay',
    dest='init_delay',
    type=int, default=60,
    help="amount of time/s to wait before starting the bootstrap process")

# ##### -------------------------
# ##### authentication
# ##### -------------------------

group = psr.add_argument_group('authentication')

group.add_argument(
    '--user', help='login user-name')

group.add_argument(
    '-U', dest='env_user',
    help='Username environment variable')

group.add_argument(
    '-P', dest='env_passwd',
    required=True,
    help='Passwd environment variable')


g_cli_args = psr.parse_args()
g_self_server = g_cli_args.server


def setup_logging(logname, logfile, target):
    log = logging.getLogger(name=logname)
    log.setLevel(logging.INFO)

    fmt = logging.Formatter(
        '%(asctime)s:%(levelname)s:{target}:%(message)s'
        .format(target=target))

    handler = logging.FileHandler(logfile) if logfile else logging.StreamHandler(sys.stdout)
    handler.setFormatter(fmt)
    log.addHandler(handler)

    return log


g_log = setup_logging(logname=_PROGNAME,
                      logfile=g_cli_args.logfile,
                      target=g_cli_args.target)


# ##### -----------------------------------------------------------------------
# #####
# #####                           Utility Functions
# #####
# ##### -----------------------------------------------------------------------

def exit_results(results, exit_error=None, dev=None, target=None):
    if results['ok']:
        post_device_status(dev=dev, target=target, state='DONE', message='bootstrap completed OK')
        sys.exit(0)
    else:
        post_device_status(dev=dev, target=target, state='ERROR', message=results['message'])
        sys.exit(exit_error or 1)


def wait_for_device(countdown, poll_delay):
    target = g_cli_args.target
    user = g_cli_args.user or os.getenv(g_cli_args.env_user)
    passwd = os.getenv(g_cli_args.env_passwd)

    if not user:
        errmsg = "login user-name missing"
        g_log.error(errmsg)
        exit_results(target=target, results=dict(
            ok=False,
            error_type='login',
            message=errmsg))

    if not passwd:
        errmsg = "login user-password missing"
        g_log.error(errmsg)
        exit_results(target=target, results=dict(
            ok=False,
            error_type='login',
            message=errmsg))

    dev = None

    # first we need to wait for the device to be 'reachable' via the API.
    # we'll use the probe error to detect if it is or not

    while not dev:
        msg = 'reload-countdown at: {} seconds'.format(countdown)
        post_device_status(target=target, state='AWAIT-ONLINE', message=msg)
        g_log.info(msg)

        try:
            dev = nxos.Device(
                target, user=user, passwd=passwd, timeout=poll_delay)

        except ProbeError:
            countdown -= poll_delay
            if countdown <= 0:
                exit_results(dict(
                    ok=False,
                    error_type='login',
                    message='Failed to probe target %s within reload countdown' % target))

        except UnauthorizedError:
            errmsg = 'Unauthorized - check user={}/passwd={}'.format(user, passwd)
            g_log.error(errmsg)
            exit_results(target=target, results=dict(
                ok=False, error_type='login', message=errmsg))

    post_device_facts(dev)

    msg = 'device reachable, waiting for System ready'
    post_device_status(dev=dev, state='AWAIT-SYSTEM-READY', message=msg)
    g_log.info(msg)

    while countdown >= 0:
        msg = 'ready-countdown at: {} seconds'.format(countdown)
        post_device_status(dev=dev, message=msg)
        g_log.info(msg)

        try:
            match = dev.api.exec_opcmd("show logging | grep 'CONF_CONTROL: System ready'",
                                       msg_type='cli_show_ascii')
            assert len(match) > 0
            return dev
        except AssertionError:
            # means that the file does not exist yet, so wait some time
            # and try again
            time.sleep(poll_delay)
            countdown -= poll_delay

    exit_results(target=target, results=dict(
        ok=False,
        error_type='login',
        message='%s failed to find "System ready" within reload countdown' % target))


# ##### -----------------------------------------------------------------------
# #####
# #####                           REST API functions
# #####
# ##### -----------------------------------------------------------------------

def post_device_facts(dev):
    requests.put(
        url='http://%s/api/devices/facts' % g_self_server,
        json=dict(
            ip_addr=dev.target,
            serial_number=dev.facts['serial_number'],
            hw_model=dev.facts['hw_model'],
            os_version=dev.facts['os_version'],
            os_name=_OS_NAME))


def post_device_status(dev=None, target=None, message=None, state=None):
    requests.put(
        url='http://%s/api/devices/status' % g_self_server,
        json=dict(
            os_name=_OS_NAME,
            ip_addr=target or dev.target,
            state=state, message=message))


# ##### -----------------------------------------------------------------------
# #####
# #####                           General config process
# #####
# ##### -----------------------------------------------------------------------

@retry(wait_fixed=5000, stop_max_attempt_number=3)
def do_push_config1(dev):
    topdir = g_cli_args.topdir
    config_dir = os.path.join(topdir, 'etc', 'configs', 'nxos')
    all_fpath = os.path.join(config_dir, 'all.conf')
    model_fpath = os.path.join(config_dir, dev.facts['hw_model'] + '.conf')
    changed = False

    post_device_status(
        dev=dev, state='CONFIG',
        message='applying general config from %s' % config_dir)

    try:
        if os.path.isfile(all_fpath):
            g_log.info('reading from: {}'.format(all_fpath))
            conf = open(all_fpath).read()
            g_log.info('pushing all config to device')
            dev.api.exec_config(conf)
            changed = True
        else:
            g_log.info('no all.conf file found')

        if os.path.isfile(model_fpath):
            g_log.info('reading model config from: {}'.format(model_fpath))
            conf = open(model_fpath).read()
            g_log.info('pushing model config to device')
            dev.api.exec_config(conf)
            changed = True
        else:
            g_log.info('no model config file found: {}'.format(model_fpath))

    except NxExc.NxosException as exc:
        g_log.critical("unable to push config: {}".format(exc.message))
        exit_results(dev=dev, results=dict(
            ok=False,
            error_type='config',
            message=exc.message))

    if changed is True:
        dev.api.exec_config("copy run start")


# ##### -----------------------------------------------------------------------
# #####
# #####                           OS install process
# #####
# ##### -----------------------------------------------------------------------

def check_os_install(dev):
    profile_dir = os.path.join(g_cli_args.topdir, 'etc', 'profiles', 'default', 'nxos')
    conf_fpath = os.path.join(profile_dir, 'os-selector.cfg')

    cmd = "{topdir}/bin/aztp_os_selector.py -j '{dev_json}' -c {config}".format(
        topdir=g_cli_args.topdir,
        dev_json=json.dumps(dev.facts),
        config=conf_fpath)

    child = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)

    _stdout, _stderr = child.communicate()
    return json.loads(_stdout)


def ensure_md5sum(filepath):
    md5sum_fpath = filepath + ".md5"

    def rd_md5sum():
        return open(md5sum_fpath).read().split()[0]

    if os.path.isfile(md5sum_fpath):
        return rd_md5sum()

    proc = subprocess.Popen('/usr/bin/md5sum {} > {}'.format(
        filepath, md5sum_fpath), shell=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    proc.communicate()
    return rd_md5sum()


def do_os_install(dev, image_name):
    vendor_dir = os.path.join(g_cli_args.topdir, 'vendor_images', _OS_NAME)
    image_fpath = os.path.join(vendor_dir, image_name)

    if not os.path.isfile(image_fpath):
        errmsg = 'image file {} does not exist'.format(image_fpath)
        exit_results(dev=dev, results=dict(
            ok=False,
            error_type='install',
            message=errmsg))

    md5sum = ensure_md5sum(filepath=image_fpath)
    msg = 'installing OS image [{}] ... please be patient'.format(image_name)
    post_device_status(dev=dev, state='OS-INSTALL', message=msg)

    cmd = "nxos-installos --target {target} --server {server} " \
          "-U {u_env} -P {p_env} --image {image} --md5sum {md5sum}".format(
              target=dev.target, server=g_cli_args.server,
              u_env=g_cli_args.env_user, p_env=g_cli_args.env_passwd,
              image=image_name, md5sum=md5sum)

    if g_cli_args.logfile:
        cmd += ' --logfile %s' % g_cli_args.logfile

    child = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
    _stdout, _stderr = child.communicate()
    return json.loads(_stdout)


def do_ensure_os_version(dev):
    os_install = check_os_install(dev)

    if not os_install['image']:
        g_log.info('no software install required')
        return dev

    g_log.info('software image install required: %s' % os_install['image'])

    got = do_os_install(dev, image_name=os_install['image'])
    if not got['ok']:
        errmsg = 'software install [{ver}] FAILED: {reason}'.format(
                 ver=os_install['image'], reason=json.dumps(got))
        g_log.critical(errmsg)
        exit_results(dict(
            ok=False,
            error_type='install',
            message=errmsg))

    g_log.info('software install OK: %s' % json.dumps(got))
    g_log.info('rebooting device ... please be patient')

    post_device_status(
        dev, state='REBOOTING',
        message='OS install OK, rebooting ... please be patient')

    time.sleep(g_cli_args.init_delay)
    return wait_for_device(countdown=g_cli_args.reload_delay, poll_delay=10)


# ##### -----------------------------------------------------------------------
# #####
# #####                           !!! MAIN !!!
# #####
# ##### -----------------------------------------------------------------------

def main():
    if not os.path.isdir(g_cli_args.topdir):
        exit_results(dict(
            ok=False,
            error_type='args',
            message='{} is not a directory'.format(g_cli_args.topdir)))

    g_log.info("starting bootstrap process in {} seconds"
               .format(g_cli_args.init_delay))

    post_device_status(
        target=g_cli_args.target,
        state='START',
        message='bootstrap started, waiting for device access')

    # first wait the init_delay amount of time ... gives the device time
    # to start the shutdown process; i.e. expect this script to be kicked
    # off from the NXOS POAP process.

    time.sleep(g_cli_args.init_delay)
    dev = wait_for_device(countdown=g_cli_args.reload_delay, poll_delay=10)

    g_log.info("proceeding with bootstrap")

    do_push_config1(dev)
    if dev.facts['virtual']:
        g_log.info('Virtual device. No OS upgrade necessary.')
    else:
        dev = do_ensure_os_version(dev)
    g_log.info("bootstrap process finished")
    exit_results(dict(ok=True), dev=dev)


if '__main__' == __name__:
    main()
