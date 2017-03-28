#!/usr/bin/env python

import sys
import os
import json
import argparse
import subprocess
import logging
import time
import requests
import hashlib

from aeon.eos.device import Device
from aeon.exceptions import ProbeError, UnauthorizedError
from aeon.exceptions import ConfigError, CommandError
from retrying import retry

_OS_NAME = 'eos'
_PROGNAME = '%s-bootstrap' % _OS_NAME
_PROGVER = '0.0.1'

# ##### -----------------------------------------------------------------------
# #####
# #####                           Command Line Arguments
# #####
# ##### -----------------------------------------------------------------------


def cli_parse(cmdargs=None):
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
        '--env_user', '-U',
        help='Username environment variable')

    group.add_argument(
        '--env_passwd', '-P',
        required=True,
        help='Passwd environment variable')

    return psr.parse_args(cmdargs)


class EosBootstrap:
    def __init__(self, server, cli_args):
        self.server = server
        self.cli_args = cli_args
        self.log = self.setup_logging(logname=_PROGNAME,
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
                os_name=_OS_NAME,
                facts=json.dumps(dev.facts)))

    def post_device_status(self, dev=None, target=None, message=None, state=None):
        if not (dev or target):
            self.log.error('Either dev or target is required to post device status. Message was: {}'.format(message))
            return
        requests.put(
            url='http://%s/api/devices/status' % self.server,
            json=dict(
                os_name=_OS_NAME,
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
                dev = Device(target, user=user, passwd=passwd, timeout=poll_delay)

            except CommandError:
                # this means that the device is probe-able, but unable to use the API
                # for some reason; likely the process is not yet ready.  need to
                # 'manually' invoke the poll delay.
                countdown -= poll_delay
                if countdown <= 0:
                    errmsg = 'Failed to access %s device API within reload countdown' % target
                    self.exit_results(target=target, exit_error=errmsg, results=dict(
                        ok=False,
                        error_type='login',
                        message=errmsg))
                time.sleep(poll_delay)

            except ProbeError:
                countdown -= poll_delay
                if countdown <= 0:
                    errmsg = 'Failed to probe target %s within reload countdown' % target
                    self.exit_results(target=target, exit_error=errmsg, results=dict(
                        ok=False,
                        error_type='login',
                        message=errmsg))

            except UnauthorizedError:
                errmsg = 'Unauthorized - check user/password'
                self.exit_results(target=target, exit_error=errmsg, results=dict(
                    ok=False,
                    error_type='login',
                    message=errmsg))

        self.post_device_facts(dev)
        return dev

    # ##### -----------------------------------------------------------------------
    # #####
    # #####                           General config process
    # #####
    # ##### -----------------------------------------------------------------------

    def do_push_config(self, dev):
        topdir = self.cli_args.topdir
        config_dir = os.path.join(topdir, 'etc', 'configs', _OS_NAME)
        all_fpath = os.path.join(config_dir, 'all.conf')
        model_fpath = os.path.join(config_dir, dev.facts['hw_model'] + '.conf')
        changed = False

        self.post_device_status(
            dev=dev, state='CONFIG',
            message='applying general config from %s' % config_dir)

        try:
            if os.path.isfile(all_fpath):
                self.log.info('reading from: {}'.format(all_fpath))
                conf = open(all_fpath).read().split('\n')
                self.log.info('pushing all config to device')
                dev.api.configure(conf)
                changed = True
            else:
                self.log.info('no all.conf file found')

            if os.path.isfile(model_fpath):
                self.log.info('reading model config from: {}'.format(model_fpath))
                conf = open(model_fpath).read().split('\n')
                self.log.info('pushing model config to device')
                dev.api.configure(conf)
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
            # retry for 5min (5000ms * 60) every 5000ms
            # because eAPI takes time to activate during boot.
            @retry(wait_fixed=5000, stop_max_attempt_number=60)
            def finalize():
                self.log.info('Saving startup-config... (This will retry until eAPI is available.)')
                dev.api.execute(['enable', 'copy running-config startup-config'])
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

        with open(md5sum_fpath, 'a') as f:
            f.write(md5sum)

        return md5sum

    def check_os_install(self, dev):
        profile_dir = os.path.join(self.cli_args.topdir, 'etc', 'profiles', 'default', _OS_NAME)
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
            results = json.loads(_stdout)

        except Exception as exc:
            errmsg = 'Unable to load os-select output as JSON: {}\n {}'.format(_stdout, str(exc))
            self.exit_results(dev=dev, exit_error=errmsg, results=dict(
                ok=False,
                error_type='config',
                message=errmsg))

        return results

    def do_os_install(self, dev, image_name):

        vendor_dir = os.path.join(self.cli_args.topdir, 'vendor_images', _OS_NAME)
        image_fpath = os.path.join(vendor_dir, image_name)

        if not os.path.isfile(image_fpath):
            errmsg = 'image file {} does not exist'.format(image_fpath)
            self.exit_results(dev=dev, results=dict(
                ok=False,
                error_type='install',
                message=errmsg))

        md5sum = self.ensure_md5sum(filepath=image_fpath)
        msg = 'installing OS image [{}] ... please be patient'.format(image_name)
        self.log.info(msg)
        self.post_device_status(dev=dev, state='OS-INSTALL', message=msg)

        # --------------------------------
        # check for file already on device
        # --------------------------------

        try:
            dev.api.execute('dir flash:%s' % image_name)
            self.log.info('file already exists on device, skipping copy.')
            has_file = True
        except CommandError:
            has_file = False

        def do_copy_file():
            # -------------------------
            # copy image file to device
            # -------------------------

            cmds = ['routing-context vrf {}'.format(dev.api.VRF_MGMT),
                    'copy http://{server}/images/{OS}/{filename} flash:'
                    .format(server=self.server, OS=_OS_NAME,
                            filename=image_name)]

            try:
                dev.api.execute(cmds)
                self.log.info('copy OS image file completed.')

            except Exception as exc:
                errmsg = "Unable to copy file to device: %s" % str(exc)
                self.log.error(errmsg)
                self.exit_results(dev=dev, results=dict(
                    ok=False,
                    error_type='install',
                    message=errmsg))

        if not has_file:
            do_copy_file()

        # -------------------
        # verify MD5 checksum
        # -------------------

        got_md5 = dev.api.execute('verify /md5 flash:{}'.format(image_name))
        has_md5 = got_md5['messages'][0].split('=')[-1].strip()
        if has_md5 != md5sum:
            errmsg = 'image file {filename} MD5 mismatch has={has} should={should}' \
                .format(filename=image_name,
                        has=has_md5, should=md5sum)

            self.log.error(errmsg)
            self.exit_results(dev=dev, results=dict(
                ok=False,
                error_type='install',
                message=errmsg))

        self.log.info('md5sum checksum OK.')

        # ---------------------------------------------
        # configure to use this version for system boot
        # ---------------------------------------------

        dev.api.configure(['boot system flash:%s' % image_name])
        dev.api.execute('copy running-config status-config')

    def do_ensure_os_version(self, dev):
        os_install = self.check_os_install(dev)
        image_name = os_install['image']
        if not image_name:
            self.log.info('no software install required')
            return dev

        self.log.info('software image install required: %s' % image_name)
        self.do_os_install(dev, image_name=image_name)

        self.log.info('software install OK')
        self.log.info('rebooting device ... please be patient')

        self.post_device_status(
            dev, state='REBOOTING',
            message='OS install %s completed, now rebooting'
                    ' ... please be patient' % image_name)

        dev.api.execute('reload now')
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

    eboot.post_device_status(
        target=cli_args.target,
        state='START',
        message='bootstrap started, waiting for device access')

    time.sleep(cli_args.init_delay)
    dev = eboot.wait_for_device(countdown=cli_args.reload_delay, poll_delay=10)

    eboot.log.info("proceeding with bootstrap")

    eboot.do_push_config(dev)
    if dev.facts['virtual']:
        eboot.log.info('Virtual device. No OS upgrade necessary.')
    else:
        eboot.do_ensure_os_version(dev)
    eboot.log.info("bootstrap process finished")
    eboot.exit_results(dict(ok=True), dev=dev)


if '__main__' == __name__:
    main()
