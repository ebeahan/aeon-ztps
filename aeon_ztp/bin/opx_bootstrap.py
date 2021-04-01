#!/usr/bin/env python

import sys
import os
import json
import argparse
import subprocess
import logging
import logging.handlers
import time

import re
import requests
import tenacity

from pexpect import pxssh
import pexpect

from aeon.opx.device import Device
from paramiko import AuthenticationException
from paramiko.ssh_exception import NoValidConnectionsError

from aeon.exceptions import LoginNotReadyError

_DEFAULTS = {
    'init-delay': 5,
    'reload-delay': 10 * 60,
}

# ##### -----------------------------------------------------------------------
# #####
# #####                           Command Line Arguments
# #####
# ##### -----------------------------------------------------------------------


def cli_parse(cmdargs=None):
    psr = argparse.ArgumentParser(
        prog='opx_bootstrap',
        description="Aeon-ZTP bootstrapper for OPX",
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
        type=int, default=_DEFAULTS['reload-delay'],
        help="about of time/s to try to reconnect to device after reload")

    psr.add_argument(
        '--init-delay',

        type=int, default=_DEFAULTS['init-delay'],
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


class OpxBootstrap(object):
    def __init__(self, server, cli_args):
        self.server = server
        self.cli_args = cli_args
        self.target = self.cli_args.target
        self.os_name = 'opx'
        self.progname = '%s-bootstrap' % self.os_name
        self.logfile = self.cli_args.logfile
        self.log = self.setup_logging(logname=self.progname, logfile=self.logfile)
        self.user, self.passwd = self.get_user_and_passwd()
        self.image_name = None
        self.finally_script = None
        self.dev = None

    def setup_logging(self, logname, logfile=None):
        log = logging.getLogger(name=logname)
        log.setLevel(logging.INFO)

        fmt = logging.Formatter(
            '%(name)s %(levelname)s {target}: %(message)s'
            .format(target=self.target))

        if logfile:
            handler = logging.FileHandler(self.logfile)
        else:
            handler = logging.handlers.SysLogHandler(address='/dev/log')
        handler.setFormatter(fmt)
        log.addHandler(handler)

        return log

    def get_ssh_session(self, user=None, password=None, onie=False, sudo=False):
        ssh = pxssh.pxssh(options={"StrictHostKeyChecking": "no", "UserKnownHostsFile": "/dev/null"})
        # Uncomment for debugging when running opx_bootstrap.py from bash
        # ssh.logfile = sys.stdout
        if password:
            ssh.login(self.target, user, password=password, auto_prompt_reset=not onie)
        else:
            ssh.login(self.target, user, auto_prompt_reset=not onie)
        if onie:
            ssh.PROMPT = 'ONIE:.*#'
        if sudo:
            rootprompt = re.compile('root@.*[#]')
            ssh.sendline('sudo -s')
            i = ssh.expect([rootprompt, 'assword.*: '])
            if i == 0:
                # Password not required
                pass
            elif i == 1:
                # Sending sudo password
                ssh.sendline(self.passwd)
                j = ssh.expect([rootprompt, 'Sorry, try again'])
                if j == 0:
                    pass
                elif j == 1:
                    errmsg = 'Bad sudo password.'
                    self.exit_results(results=dict(
                        ok=False,
                        error_type='install',
                        message=errmsg))
            else:
                errmsg = 'Unable to obtain root privileges.'
                self.exit_results(results=dict(
                    ok=False,
                    error_type='install',
                    message=errmsg))
            ssh.set_unique_prompt()
            ssh.sendline('whoami')
            ssh.expect('root')
            self.log.info('Logged in as root')
        ssh.sendline('\n')
        ssh.prompt()
        return ssh

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
        if not (self.dev or self.target):
            self.log.error('Either dev or target is required to post device status. Message was: {}'.format(message))
            return
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
            msg = 'bootstrap completed OK'
            self.post_device_status(message=msg, state='DONE')
            self.log.info(msg)
            sys.exit(0)
        else:
            msg = results['message']
            self.post_device_status(message=msg, state='FAILED')
            self.log.error(msg)
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

    def wait_for_device(self, countdown, poll_delay, msg=None):
        dev = None

        # first we need to wait for the device to be 'reachable' via the API.
        # we'll use the probe error to detect if it is or not

        while not dev:

            new_msg = msg or 'Waiting for device access via SSH. Timeout remaining: {} seconds'.format(countdown)
            self.post_device_status(message=new_msg, state='AWAIT-ONLINE')
            self.log.info(new_msg)

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

            except LoginNotReadyError as e:
                countdown -= poll_delay
                if countdown <= 0:
                    self.exit_results(results=dict(
                        ok=False,
                        error_type='login',
                        message='Failed to connect to target %s within reload countdown' % self.target))

                time.sleep(poll_delay)

        self.dev = dev
        self.post_device_facts()

    def wait_for_onie_rescue(self, countdown, poll_delay, user='root'):
        """Polls for SSH access to OPX device in ONIE rescue mode.

        Args:
            countdown (int): Countdown in seconds to wait for device to become reachable.
            poll_delay (int): Countdown in seconds between poll attempts.
            user (str): SSH username to use. Defaults to 'root'.

        """

        while countdown >= 0:
            try:
                msg = 'OPX installation in progress. Waiting for ONIE rescue mode. Timeout remaining: {} seconds'.format(
                    countdown)
                self.post_device_status(message=msg, state='AWAIT-ONLINE')
                self.log.info(msg)
                ssh = pxssh.pxssh(options={"StrictHostKeyChecking": "no", "UserKnownHostsFile": "/dev/null"})
                ssh.login(self.target, user, auto_prompt_reset=False)
                ssh.PROMPT = 'ONIE:.*#'
                ssh.sendline('\n')
                ssh.prompt()

                return True
            except (pexpect.pxssh.ExceptionPxssh, pexpect.exceptions.EOF) as e:
                if (str(e) == 'Could not establish connection to host') or isinstance(e, pexpect.exceptions.EOF):
                    countdown -= poll_delay
                    time.sleep(poll_delay)
                else:
                    self.log.error('Error accessing {} in ONIE rescue mode: {}.'.format(self.target, str(e)))
                    self.exit_results(results=dict(
                        ok=False,
                        error_type='login',
                        message='Error accessing {} in ONIE rescue mode: {}.'.format(self.target, str(e))))
        else:
            self.log.error('Device {} not reachable in ONIE rescue mode within reload countdown.'.format(self.target))
            self.exit_results(results=dict(
                ok=False,
                error_type='login',
                message='Device {} not reachable in ONIE rescue mode within reload countdown.'.format(self.target)))

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
            image_name = results.get('image_name', None)
            finally_script = results.get('finally', None)

            self.image_name = image_name
            self.finally_script = finally_script

            self.post_device_facts()
            return results

        except Exception as exc:
            errmsg = 'Unable to load os-select output as JSON: {}\n {}'.format(_stdout, str(exc))
            self.exit_results(results=dict(
                ok=False,
                error_type='install',
                message=errmsg
            ), exit_error=errmsg)

    # Cannot mock out retry decorator in unittest.
    # Retry wrapper function around do_onie_install to avoid long unittest times.
    @tenacity.retry(wait=tenacity.wait_fixed(15000), stop=tenacity.stop_after_attempt(3))
    def onie_install(self, *args, **kwargs):
        self.do_onie_install(**kwargs)

    def do_onie_install(self, user='root'):
        """Initiates install in ONIE-RESCUE mode.

        Args:
            dev (Device object): OPX device object
            user (str): ONIE rescue mode user
        """

        msg = 'Beginning OPX download and installation.'
        self.post_device_status(message=msg, state='ONIE-RESCUE')
        self.log.info(msg)
        ssh = self.get_ssh_session(user=user, onie=True)

        def start_installation():
            # Start installation process
            ssh.sendline('onie-nos-install http://{server}/images/{os_name}/{image_name}'
                         .format(server=self.cli_args.server, os_name=self.os_name, image_name=self.image_name))

            # 'installer' means that the download has started
            ssh.expect('installer', timeout=30)

            msg = 'OPX image download has started. Will timeout if not completed within 10 minutes.'
            self.log.info(msg)
            self.post_device_status(message=msg, state='OS-INSTALL')

            check_install_status()

            msg = 'OPX download complete. Executing installer. Will timeout if not completed within 20 minutes.'
            self.log.info(msg)
            self.post_device_status(message=msg, state='OS-INSTALL')

            # Indicates that the image has been downloaded and verified
            ssh.expect('Installation finished. No error reported.', timeout=20 * 60)
            ssh.prompt()
            ssh.sendline('reboot')
            msg = 'OPX download completed and verified, reboot initiated.'
            self.log.info(msg)
            self.post_device_status(message=msg, state='OS-INSTALL')
            ssh.close()

        @tenacity.retry(wait=tenacity.wait_fixed(5),
                        stop=tenacity.stop_after_delay(10 * 60),
                        retry=tenacity.retry_if_exception(pexpect.exceptions.TIMEOUT))
        def check_install_status():
            """
            Check to see that either the install has started, or that the download has timed out.
            :return:
            """
            # 'Executing installer' means that the download has finished
            i = ssh.expect(['Verifying image checksum...OK', 'download timed out'], timeout=5)
            if i == 0:
                pass
            if i == 1:
                msg = 'Download timed out: http://{server}/images/{os_name}/{image_name}'.format(
                    server=self.cli_args.server, os_name=self.os_name, image_name=self.image_name)
                self.log.info(msg)
                self.exit_results(results=dict(ok=False, error_type='install', message=msg))

        try:
            start_installation()

        except pxssh.ExceptionPxssh as e:
            self.log.info(str(e))
            self.exit_results(results=dict(ok=False, error_type='install', message=str(e)))

    def install_os(self):
        vendor_dir = os.path.join(self.cli_args.topdir, 'vendor_images', self.os_name)

        image_fpath = os.path.join(vendor_dir, self.image_name)
        if not os.path.exists(image_fpath):
            errmsg = 'Image file does not exist: %s' % image_fpath
            self.log.error(errmsg)
            self.exit_results(results=dict(
                ok=False, error_type='install',
                message=errmsg))

        msg = 'Installing OPX image=[%s] ... this can take up to 30 min.' % self.image_name
        self.log.info(msg)
        self.post_device_status(message=msg, state='OS-INSTALL')
        try:
            ssh = self.get_ssh_session(user=self.user, password=self.passwd, sudo=True)
            ssh.sendline('grub-reboot --boot-directory=/mnt/boot ONIE')
            ssh.prompt()
            ssh.sendline('/mnt/onie-boot/onie/tools/bin/onie-boot-mode -o rescue')
            ssh.prompt()
            ssh.sendline('reboot')

        except pxssh.ExceptionPxssh as e:
            self.log.info(str(e))
            self.exit_results(results=dict(ok=False, error_type='install', message=str(e)))

        msg = 'Booting into ONIE rescue mode to install OS: %s' % self.image_name
        self.log.info(msg)
        self.post_device_status(message=msg, state='OS-INSTALL')
        time.sleep(60)

        # Wait for ONIE rescue mode
        self.wait_for_onie_rescue(countdown=300, poll_delay=10, user='root')

        # Download and verify OS
        self.onie_install()

        # Wait for onie-rescue shell to terminate
        time.sleep(60)

        # Wait for device to come back online after OS install
        self.wait_for_device(countdown=10 * 60, poll_delay=30)

    def ensure_os_version(self):
        self.check_os_install_and_finally()
        if not self.image_name:
            self.log.info('no software install required')
            return self.dev

        self.log.info('software image install required: %s' % self.image_name)
        self.install_os()

        self.log.info('software install OK')


# ##### -----------------------------------------------------------------------
# #####
# #####                           !!! MAIN !!!
# #####
# ##### -----------------------------------------------------------------------

def main():
    cli_args = cli_parse()
    self_server = cli_args.server
    opxboot = OpxBootstrap(self_server, cli_args)
    if not os.path.isdir(cli_args.topdir):
        opxboot.exit_results(dict(
            ok=False,
            error_type='args',
            message='{} is not a directory'.format(cli_args.topdir)))

    opxboot.post_device_status(message='bootstrap started, waiting for device access', state='START')

    opxboot.wait_for_device(countdown=cli_args.reload_delay, poll_delay=10, msg='Waiting for device access')
    # Give the device time to stabilize since SSH may not be reliable yet.
    time.sleep(30)

    opxboot.log.info("proceeding with bootstrap")

    if opxboot.dev.facts['virtual']:
        opxboot.log.info('Virtual device. No OS upgrade necessary.')
        opxboot.check_os_install_and_finally()
    else:
        opxboot.ensure_os_version()
    opxboot.log.info("bootstrap process finished")
    opxboot.exit_results(dict(ok=True))


if '__main__' == __name__:
    main()
