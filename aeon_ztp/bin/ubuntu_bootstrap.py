#!/usr/bin/env python

import sys
import os
import json
import argparse
import subprocess
import logging
import time
import requests

from aeon.cumulus.device import Device
from paramiko import AuthenticationException
from paramiko.ssh_exception import NoValidConnectionsError


# ##### -----------------------------------------------------------------------
# #####
# #####                           Command Line Arguments
# #####
# ##### -----------------------------------------------------------------------

def cli_parse(cmdargs=None):
    psr = argparse.ArgumentParser(
        description="Aeon-ZTP bootstrapper for Ubuntu Linux",
        add_help=True)

    psr.add_argument(
        '--target', required=True,
        help='hostname or ip_addr of target device')

    psr.add_argument(
        '--server', required=True,
        help='Aeon-ZTP host:port')

    psr.add_argument(
        '--topdir', required=True,
        help='Aeon-ZTP install directory')

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
        type=int, default=5,
        help="amount of time/s to wait before starting the bootstrap process")

    # ##### -------------------------
    # ##### authentication
    # ##### -------------------------

    group = psr.add_argument_group('authentication')

    group.add_argument(
        '--user', help='login user-name')

    group.add_argument(
        '-U', '--env-user',
        help='Username environment variable')

    group.add_argument(
        '-P', '--env-passwd',
        required=True,
        help='Passwd environment variable')

    return psr.parse_args(cmdargs)


class UbuntuBootstrap:
    def __init__(self, server, cli_args):
        self.progname = 'ubuntu-bootstrap'
        self.progver = '0.0.1'
        self.os_name = 'ubuntu'
        self.server = server
        self.cli_args = cli_args
        self.log = self.setup_logging(logname=self.progname,
                                      logfile=self.cli_args.logfile,
                                      target=self.cli_args.target)

    @staticmethod
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

    # ##### -----------------------------------------------------------------------
    # #####
    # #####                           REST API functions
    # #####
    # ##### -----------------------------------------------------------------------

    def post_device_facts(self, dev):
        requests.put(
            url='http://%s/api/devices/facts' % self.server,
            json=dict(
                ip_addr=dev.target,
                serial_number=dev.facts['serial_number'],
                hw_model=dev.facts['hw_model'],
                os_version=dev.facts['os_version'],
                os_name=self.os_name))

    def post_device_status(self, dev=None, target=None, message=None, state=None):
        requests.put(
            url='http://%s/api/devices/status' % self.server,
            json=dict(
                os_name=self.os_name,
                ip_addr=target or dev.target,
                state=state, message=message))

    # ##### -----------------------------------------------------------------------
    # #####
    # #####                           Utility Functions
    # #####
    # ##### -----------------------------------------------------------------------

    def exit_results(self, results, exit_error=None, dev=None, target=None):
        if results['ok']:
            self.post_device_status(dev=dev, target=target, state='DONE', message='bootstrap completed OK')
            sys.exit(0)
        else:
            self.post_device_status(dev=dev, target=target, state='ERROR', message=results['message'])
            sys.exit(exit_error or 1)

    def wait_for_device(self, countdown, poll_delay):
        target = self.cli_args.target
        user = self.cli_args.user or os.getenv(self.cli_args.env_user)
        passwd = os.getenv(self.cli_args.env_passwd)

        if not user:
            errmsg = "login user-name missing"
            self.log.error(errmsg)
            self.exit_results(target=target, results=dict(
                ok=False,
                error_type='login',
                message=errmsg))

        if not passwd:
            errmsg = "login user-password missing"
            self.log.error(errmsg)
            self.exit_results(target=target, results=dict(
                ok=False,
                error_type='login',
                message=errmsg))

        dev = None

        # first we need to wait for the device to be 'reachable' via the API.
        # we'll use the probe error to detect if it is or not

        while not dev:
            msg = 'reload-countdown at: {} seconds'.format(countdown)
            self.post_device_status(target=target, state='AWAIT-ONLINE', message=msg)
            self.log.info(msg)

            try:
                dev = Device(target, user=user, passwd=passwd,
                             timeout=poll_delay)

            except AuthenticationException as e:
                self.log.info('Authentication exception reported: {} \n args: {}'.format(e, e.args))
                self.exit_results(target=target, results=dict(
                    ok=False,
                    error_type='login',
                    message='Unauthorized - check user/password'))

            except NoValidConnectionsError as e:
                countdown -= poll_delay
                if countdown <= 0:
                    self.exit_results(target=target, results=dict(
                        ok=False,
                        error_type='login',
                        message='Failed to connect to target %s within reload countdown' % target))

                time.sleep(poll_delay)

        self.post_device_facts(dev)
        return dev

    # ##### -----------------------------------------------------------------------
    # #####
    # #####                           OS install process
    # #####
    # ##### -----------------------------------------------------------------------

    def get_required_os(self, dev):
        profile_dir = os.path.join(self.cli_args.topdir, 'etc', 'profiles', 'default', self.os_name)
        conf_fpath = os.path.join(profile_dir, 'os-selector.cfg')

        cmd = "{topdir}/bin/aztp_os_selector.py -j '{dev_json}' -c {config}".format(
            topdir=self.cli_args.topdir,
            dev_json=json.dumps(dev.facts),
            config=conf_fpath)

        self.log.info('os-select: [%s]' % cmd)

        child = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)

        _stdout, _stderr = child.communicate()
        self.log.info('os-select rc={}, stdout={}'.format(child.returncode, _stdout))
        self.log.info('os-select stderr={}'.format(_stderr))

        try:
            return json.loads(_stdout)

        except Exception:
            errmsg = 'Unable to load os-select output as JSON: {}'.format(_stdout)
            self.exit_results(dev=dev, results=dict(
                ok=False,
                error_type='install',
                message=errmsg))

    def install_os(self, dev, image_name):
        vendor_dir = os.path.join(self.cli_args.topdir, 'vendor_images', self.os_name)

        image_fpath = os.path.join(vendor_dir, image_name)
        if not os.path.exists(image_fpath):
            errmsg = 'image file does not exist: %s' % image_fpath
            self.log.error(errmsg)
            self.exit_results(dev=dev, results=dict(
                ok=False, error_type='install',
                message=errmsg))

        msg = 'installing OS image=[%s] ... please be patient' % image_name
        self.log.info(msg)
        self.post_device_status(dev=dev, state='OS-INSTALL', message=msg)

        install_command = 'sudo /usr/cumulus/bin/cl-img-install -sf ' \
                          'http://{server}/images/{os_name}/{image_name}'.format(server=self.cli_args.server,
                                                                                 os_name=self.os_name,
                                                                                 image_name=image_name)
        all_good, results = dev.api.execute([install_command])

        if not all_good:
            errmsg = 'Unable to run command: {}. Error message: {}'.format(install_command, results)
            self.exit_results(dev=dev, results=dict(
                ok=False,
                error_type='install',
                message=errmsg))

    def ensure_os_version(self, dev):
        os_install = self.get_required_os(dev)

        if not os_install['image']:
            self.log.info('no software install required')
            return dev

        self.log.info('software image install required: %s' % os_install['image'])
        self.install_os(dev, image_name=os_install['image'])

        self.log.info('software install OK')
        self.log.info('rebooting device ... please be patient')

        self.post_device_status(
            dev, state='OS-REBOOTING',
            message='OS install completed, now rebooting ... please be patient')

        dev.api.execute(['sudo reboot'])
        time.sleep(self.cli_args.init_delay)
        return self.wait_for_device(countdown=self.cli_args.reload_delay, poll_delay=10)


# ##### -----------------------------------------------------------------------
# #####
# #####                           !!! MAIN !!!
# #####
# ##### -----------------------------------------------------------------------

def main():
    cli_args = cli_parse()
    server = cli_args.server
    uboot = UbuntuBootstrap(server, cli_args)
    if not os.path.isdir(cli_args.topdir):
        uboot.exit_results(dict(
            ok=False,
            error_type='args',
            message='{} is not a directory'.format(cli_args.topdir)))

    uboot.log.info("bootstrap init-delay: {} seconds".format(cli_args.init_delay))

    uboot.post_device_status(
        target=cli_args.target,
        state='START',
        message='bootstrap started, waiting for device access')

    time.sleep(cli_args.init_delay)
    dev = uboot.wait_for_device(countdown=cli_args.reload_delay, poll_delay=10)

    uboot.log.info("bootstrap process finished")
    uboot.exit_results(dict(ok=True), dev=dev)


if '__main__' == __name__:
    main()
