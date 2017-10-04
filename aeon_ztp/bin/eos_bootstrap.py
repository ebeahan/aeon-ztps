#!/usr/bin/env python

import sys
import os
import json
import argparse
import subprocess
import logging
import logging.handlers
import tempfile
import time
import requests
import hashlib

from aeon.eos.device import Device
from aeon.exceptions import ProbeError, UnauthorizedError
from aeon.exceptions import ConfigError, CommandError
from retrying import retry


# ##### -----------------------------------------------------------------------
# #####
# #####                           Command Line Arguments
# #####
# ##### -----------------------------------------------------------------------


def cli_parse(cmdargs=None):
    psr = argparse.ArgumentParser(
        prog='eos_bootstrap',
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
        help='toplevel directory aztp installation files')

    psr.add_argument(
        '--logfile',
        help='name of log file')

    psr.add_argument(
        '--reload-delay',
        type=int, default=10 * 60,
        help="about of time/s to try to reconnect to device after reload")

    psr.add_argument(
        '--init-delay',
        type=int, default=60,
        help="amount of time/s to wait before starting the bootstrap process")

    # ##### -------------------------
    # ##### authentication
    # ##### -------------------------

    group = psr.add_argument_group('authentication')

    group.add_argument(
        '--user', help='login user-name')

    group.add_argument(
        '--env-user', '-U',
        help='Username environment variable')

    group.add_argument(
        '--env-passwd', '-P',
        required=True,
        help='Passwd environment variable')

    return psr.parse_args(cmdargs)


class EosBootstrap(object):
    def __init__(self, server, cli_args):
        self.server = server
        self.cli_args = cli_args
        self.target = self.cli_args.target
        self.os_name = 'eos'
        self.progname = '%s-bootstrap' % self.os_name
        self.logfile = self.cli_args.logfile
        self.log = self.setup_logging(logname=self.progname)
        self.user, self.passwd = self.get_user_and_passwd()
        self.image_name = None
        self.finally_script = None
        self.dev = None
        self.vendor_dir = os.path.join(self.cli_args.topdir, 'vendor_images', self.os_name)
        self.image_fpath = None

    def setup_logging(self, logname):
        log = logging.getLogger(name=logname)
        log.setLevel(logging.INFO)

        fmt = logging.Formatter(
            '%(name)s %(levelname)s {target}: %(message)s'
            .format(target=self.target))

        handler = logging.handlers.SysLogHandler(address='/dev/log')
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
            self.post_device_status(message='bootstrap completed OK', state='DONE')
            sys.exit(0)
        else:
            self.post_device_status(message=results['message'], state='FAILED')
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
                dev = Device(self.target, user=self.user, passwd=self.passwd, timeout=poll_delay)

            except CommandError:
                # this means that the device is probe-able, but unable to use the API
                # for some reason; likely the process is not yet ready.  need to
                # 'manually' invoke the poll delay.
                countdown -= poll_delay
                if countdown <= 0:
                    errmsg = 'Failed to access %s device API within reload countdown' % self.target
                    self.exit_results(results=dict(
                        ok=False,
                        error_type='login',
                        message=errmsg), exit_error=errmsg)
                time.sleep(poll_delay)

            except ProbeError:
                countdown -= poll_delay
                if countdown <= 0:
                    errmsg = 'Failed to probe target %s within reload countdown' % self.target
                    self.exit_results(results=dict(
                        ok=False,
                        error_type='login',
                        message=errmsg), exit_error=errmsg)

            except UnauthorizedError:
                errmsg = 'Unauthorized - check user/password'
                self.exit_results(results=dict(
                    ok=False,
                    error_type='login',
                    message=errmsg), exit_error=errmsg)

        self.dev = dev
        self.post_device_facts()

    # ##### -----------------------------------------------------------------------
    # #####
    # #####                           General config process
    # #####
    # ##### -----------------------------------------------------------------------

    def do_push_config(self):
        topdir = self.cli_args.topdir
        config_dir = os.path.join(topdir, 'etc', 'configs', self.os_name)
        all_fpath = os.path.join(config_dir, 'all.conf')
        model_fpath = os.path.join(config_dir, self.dev.facts['hw_model'] + '.conf')
        changed = False

        self.post_device_status(message='applying general config from %s' % config_dir, state='CONFIG')

        try:
            if os.path.isfile(all_fpath):
                self.log.info('reading from: {}'.format(all_fpath))
                conf = open(all_fpath).read().split('\n')
                self.log.info('pushing all config to device')
                self.dev.api.configure(conf)
                changed = True
            else:
                self.log.info('no all.conf file found')

            if os.path.isfile(model_fpath):
                self.log.info('reading model config from: {}'.format(model_fpath))
                conf = open(model_fpath).read().split('\n')
                self.log.info('pushing model config to device')
                self.dev.api.configure(conf)
                changed = True
            else:
                self.log.info('no model config file found: {}'.format(model_fpath))

        except ConfigError as exc:
            errmsg = str(exc.exc)
            self.log.critical("unable to push config: {}".format(errmsg))
            self.exit_results(dict(
                ok=False,
                error_type='config',
                message=errmsg))

        if changed is True:
            self.post_device_status(message='Waiting for eAPI to become available.', state='CONFIG')

            # retry for 5min (5000ms * 60) every 5000ms
            # because eAPI takes time to activate during boot.

            @retry(wait_fixed=5000, stop_max_attempt_number=60)
            def finalize():
                self.log.info('Saving startup-config... (This will retry until eAPI is available.)')
                self.dev.api.execute(['enable', 'copy running-config startup-config'])
                self.post_device_status(message='Config written to device.', state='CONFIG')
                self.log.info('config completed OK.')
            finalize()

    # ##### -----------------------------------------------------------------------
    # #####
    # #####                           OS install process
    # #####
    # ##### -----------------------------------------------------------------------
    @staticmethod
    def ensure_md5sum(filepath):
        md5sum_fpath = filepath + ".md5"

        if os.path.isfile(md5sum_fpath):
            with open(md5sum_fpath, 'rb') as f:
                return f.read()

        with open(filepath, 'rb') as f:
            md5sum = hashlib.md5(f.read()).hexdigest()

        with tempfile.NamedTemporaryFile('w', dir=os.path.dirname(md5sum_fpath), delete=False) as tf:
            tf.write(md5sum)
            tempname = tf.name

        os.rename(tempname, md5sum_fpath)

        return md5sum

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

    @retry(stop_max_attempt_number=10, wait_fixed=1000, stop_max_delay=600000)
    def do_os_install(self):
        self.image_fpath = os.path.join(self.vendor_dir, self.image_name)
        if not os.path.isfile(self.image_fpath):
            errmsg = 'Image file {} does not exist'.format(self.image_fpath)
            self.log.critical(errmsg)
            self.exit_results(results=dict(
                ok=False,
                error_type='install',
                message=errmsg))

        msg = 'installing OS image [{}] ... please be patient'.format(self.image_name)
        self.log.info(msg)
        self.post_device_status(message=msg, state='OS-INSTALL')

        # --------------------------------
        # check for file already on device
        # --------------------------------

        try:
            self.dev.api.execute('dir flash:%s' % self.image_name)
            self.log.info('file already exists on device, skipping copy.')
            has_file = True
        except CommandError:
            has_file = False

        if has_file:
            # ---------------------------------------------
            # Configure switch to boot from existing upgrade image
            # ---------------------------------------------
            self.check_md5()
            self.dev.api.configure(['boot system flash:%s' % self.image_name])

        else:
            # Install directly from ZTPS, bypassing the need to copy first
            # Note that even if the install fails, this image will persist in flash.
            # The next retry attempt will not have to download the image again.
            cmds = ['install source http://{server}/images/{OS}/{filename}'
                    .format(server=self.server, OS=self.os_name,
                            filename=self.image_name)]
            try:
                self.dev.api.execute(cmds)
            except CommandError as e:
                self.log.error('Error while installing image: {}'.format(str(e)))
            self.check_md5()

        # Write config
        self.dev.api.execute('copy running-config startup-config')
        return

    def check_md5(self):
        """"""
        md5sum = self.ensure_md5sum(filepath=self.image_fpath)
        got_md5 = self.dev.api.execute('verify /md5 flash:{}'.format(self.image_name))
        has_md5 = got_md5['messages'][0].split('=')[-1].strip()
        if has_md5 != md5sum:
            errmsg = 'Image file {filename} MD5 mismatch has={has} should={should}' \
                .format(filename=self.image_name,
                        has=has_md5, should=md5sum)

            self.log.error(errmsg)
            self.exit_results(results=dict(
                ok=False,
                error_type='install',
                message=errmsg))

        self.log.info('md5sum checksum OK.')

    def do_ensure_os_version(self):
        self.check_os_install_and_finally()
        if not self.image_name:
            self.log.info('no software install required')
            return self.dev

        self.log.info('software image install required: %s' % self.image_name)
        self.do_os_install()

        self.log.info('software install OK')
        self.log.info('rebooting device ... please be patient')

        self.post_device_status(message='OS install %s completed, now rebooting'
                                        ' ... please be patient' % self.image_name, state='REBOOTING')

        try:
            self.dev.api.execute('reload now')
        except CommandError:
            # Ignore errors during disconnect due to reboot
            pass

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
    eboot = EosBootstrap(server, cli_args)
    if not os.path.isdir(cli_args.topdir):
        eboot.exit_results(dict(
            ok=False,
            error_type='args',
            message='{} is not a directory'.format(cli_args.topdir)))

    eboot.log.info("starting bootstrap process in {} seconds"
               .format(cli_args.init_delay))

    eboot.post_device_status(message='bootstrap started, waiting for device access', state='START')

    time.sleep(cli_args.init_delay)
    eboot.wait_for_device(countdown=cli_args.reload_delay, poll_delay=10)

    eboot.log.info("proceeding with bootstrap")

    eboot.do_push_config()
    if eboot.dev.facts['virtual']:
        eboot.log.info('Virtual device. No OS upgrade necessary.')
        eboot.check_os_install_and_finally()
    else:
        eboot.do_ensure_os_version()
    eboot.log.info("bootstrap process finished")
    eboot.exit_results(dict(ok=True))


if '__main__' == __name__:
    main()
