#!/usr/bin/env python

import sys
import os
import json
import argparse
import subprocess
import logging
import time
import requests

from aeon.ubuntu.device import Device
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


class UbuntuBootstrap(object):
    def __init__(self, server, cli_args):
        self.server = server
        self.cli_args = cli_args
        self.target = self.cli_args.target
        self.os_name = 'ubuntu'
        self.progname = 'ubuntu-bootstrap'
        self.logfile = self.cli_args.logfile
        self.log = self.setup_logging(logname=self.progname)
        self.user, self.passwd = self.get_user_and_passwd()
        self.image_name = None
        self.finally_script = None
        self.dev = None

    def setup_logging(self, logname):
        log = logging.getLogger(name=logname)
        log.setLevel(logging.INFO)

        fmt = logging.Formatter(
            '%(asctime)s:%(levelname)s:{target}:%(message)s'
            .format(target=self.target))

        handler = logging.FileHandler(self.logfile) if self.logfile else logging.StreamHandler(sys.stdout)
        handler.setFormatter(fmt)
        log.addHandler(handler)

        return log

    # ##### -----------------------------------------------------------------------
    # #####
    # #####                           REST API functions
    # #####
    # ##### -----------------------------------------------------------------------

    def post_device_facts(self):
        facts = self.dev.facts
        facts['ip_addr'] = self.dev.target
        facts = json.dumps(facts)
        dev_data = dict(
            ip_addr=self.dev.target,
            serial_number=self.dev.facts['serial_number'],
            hw_model=self.dev.facts['hw_model'],
            os_version=self.dev.facts['os_version'],
            os_name=self.os_name,
            facts=facts)
        dev_data['image_name'] = self.image_name
        dev_data['finally_script'] = self.finally_script

        requests.put(url='http://%s/api/devices/facts' % self.server, json=dev_data)

    def post_device_status(self, message=None, state=None):
        requests.put(
            url='http://%s/api/devices/status' % self.server,
            json=dict(
                os_name=self.os_name,
                ip_addr=self.target or self.dev.target,
                state=state, message=message))

    # ##### -----------------------------------------------------------------------
    # #####
    # #####                           Utility Functions
    # #####
    # ##### -----------------------------------------------------------------------

    def exit_results(self, results, exit_error=None):
        if results['ok']:
            self.post_device_status(message='bootstrap completed OK', state='DONE')
            sys.exit(0)
        else:
            self.post_device_status(message=results['message'], state='ERROR')
            sys.exit(exit_error or 1)

    def get_user_and_passwd(self):
        user = self.cli_args.user or os.getenv(self.cli_args.env_user)
        passwd = os.getenv(self.cli_args.env_passwd)

        if not user:
            errmsg = "login user-name missing"
            self.log.error(errmsg)
            self.exit_results(results=dict(
                ok=False,
                error_type='login',
                message=errmsg))

        if not passwd:
            errmsg = "login user-password missing"
            self.log.error(errmsg)
            self.exit_results(results=dict(
                ok=False,
                error_type='login',
                message=errmsg))

        return user, passwd

    def wait_for_device(self, countdown, poll_delay):

        dev = None

        # first we need to wait for the device to be 'reachable' via the API.
        # we'll use the probe error to detect if it is or not

        while not dev:
            msg = 'reload-countdown at: {} seconds'.format(countdown)
            self.post_device_status(message=msg, state='AWAIT-ONLINE')
            self.log.info(msg)

            try:
                dev = Device(self.target, user=self.user, passwd=self.passwd,
                             timeout=poll_delay)

            except AuthenticationException as e:
                self.log.info('Authentication exception reported: {} \n args: {}'.format(e, e.args))
                self.exit_results(results=dict(
                    ok=False,
                    error_type='login',
                    message='Unauthorized - check user/password'))

            except NoValidConnectionsError as e:
                countdown -= poll_delay
                if countdown <= 0:
                    self.exit_results(results=dict(
                        ok=False,
                        error_type='login',
                        message='Failed to connect to target %s within reload countdown' % self.target))

                time.sleep(poll_delay)

        self.dev = dev
        self.post_device_facts()

    # ##### -----------------------------------------------------------------------
    # #####
    # #####                           OS install process
    # #####
    # ##### -----------------------------------------------------------------------

    def check_os_install_and_finally(self):
        profile_dir = os.path.join(self.cli_args.topdir, 'etc', 'profiles', self.os_name)
        conf_fpath = os.path.join(profile_dir, 'os-selector.cfg')

        cmd = "{topdir}/bin/aztp_os_selector.py -j '{dev_json}' -c {config}".format(
            topdir=self.cli_args.topdir,
            dev_json=json.dumps(self.dev.facts),
            config=conf_fpath)

        self.log.info('os-select: [%s]' % cmd)

        child = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)

        _stdout, _stderr = child.communicate()
        self.log.info('os-select rc={}, stdout={}'.format(child.returncode, _stdout))
        self.log.info('os-select stderr={}'.format(_stderr))

        try:
            results = json.loads(_stdout)
            image = results.get('image', None)
            finally_script = results.get('finally', None)

            self.image_name = image
            self.finally_script = finally_script

            self.post_device_facts()
            return results

        except Exception as exc:
            errmsg = 'Unable to load os-select output as JSON: {}\n {}'.format(_stdout, str(exc))
            self.exit_results(
                results=dict(
                    ok=False,
                    error_type='install',
                    message=errmsg
                ),
                exit_error=errmsg
            )


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

    uboot.post_device_status(message='bootstrap started, waiting for device access', state='START')

    time.sleep(cli_args.init_delay)
    uboot.wait_for_device(countdown=cli_args.reload_delay, poll_delay=10)

    uboot.log.info("proceeding with bootstrap")

    uboot.check_os_install_and_finally()
    uboot.log.info("bootstrap process finished")
    uboot.exit_results(dict(ok=True))


if '__main__' == __name__:
    main()
