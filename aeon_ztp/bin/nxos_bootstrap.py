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
import hashlib

from aeon.nxos.device import Device
import aeon.nxos.exceptions as NxExc
from aeon.exceptions import ProbeError, UnauthorizedError


# ##### -----------------------------------------------------------------------
# #####
# #####                           Command Line Arguments
# #####
# ##### -----------------------------------------------------------------------

def cli_parse(cmdargs=None):
    psr = argparse.ArgumentParser(
        description="Aeon ZTP bootstrapper for NXOS",
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


class NxosBootstrap:
    def __init__(self, server, cli_args):
        self.os_name = 'nxos'
        self.progname = '%s-bootstrap' % self.os_name
        self.progver = '0.0.1'
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
                dev = Device(
                    target, user=user, passwd=passwd, timeout=poll_delay)

            except ProbeError:
                countdown -= poll_delay
                if countdown <= 0:
                    self.exit_results(dict(
                        ok=False,
                        error_type='login',
                        message='Failed to probe target %s within reload countdown' % target))

            except UnauthorizedError:
                errmsg = 'Unauthorized - check user={}/passwd={}'.format(user, passwd)
                self.log.error(errmsg)
                self.exit_results(target=target, results=dict(
                    ok=False, error_type='login', message=errmsg))

        self.post_device_facts(dev)

        msg = 'device reachable, waiting for System ready'
        self.post_device_status(dev=dev, state='AWAIT-SYSTEM-READY', message=msg)
        self.log.info(msg)

        while countdown >= 0:
            msg = 'ready-countdown at: {} seconds'.format(countdown)
            self.post_device_status(dev=dev, message=msg)
            self.log.info(msg)

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

        self.exit_results(target=target, results=dict(
            ok=False,
            error_type='login',
            message='%s failed to find "System ready" within reload countdown' % target))

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
                os_name=self.os_name,
                facts=json.dumps(dev.facts)))

    def post_device_status(self, dev=None, target=None, message=None, state=None):
        if not (dev or target):
            self.log.error('Either dev or target is required to post device status. Message was: {}'.format(message))
            return
        requests.put(
            url='http://%s/api/devices/status' % self.server,
            json=dict(
                os_name=self.os_name,
                ip_addr=target or dev.target,
                state=state, message=message))

    # ##### -----------------------------------------------------------------------
    # #####
    # #####                           General config process
    # #####
    # ##### -----------------------------------------------------------------------

    @retry(wait_fixed=5000, stop_max_attempt_number=3)
    def do_push_config1(self, dev):
        topdir = self.cli_args.topdir
        config_dir = os.path.join(topdir, 'etc', 'configs', 'nxos')
        all_fpath = os.path.join(config_dir, 'all.conf')
        model_fpath = os.path.join(config_dir, dev.facts['hw_model'] + '.conf')
        changed = False

        self.post_device_status(
            dev=dev, state='CONFIG',
            message='applying general config from %s' % config_dir)

        try:
            if os.path.isfile(all_fpath):
                self.log.info('reading from: {}'.format(all_fpath))
                conf = open(all_fpath).read()
                self.log.info('pushing all config to device')
                dev.api.exec_config(conf)
                changed = True
            else:
                self.log.info('no all.conf file found')

            if os.path.isfile(model_fpath):
                self.log.info('reading model config from: {}'.format(model_fpath))
                conf = open(model_fpath).read()
                self.log.info('pushing model config to device')
                dev.api.exec_config(conf)
                changed = True
            else:
                self.log.info('no model config file found: {}'.format(model_fpath))

        except NxExc.NxosException as exc:
            self.log.critical("unable to push config: {}".format(exc.message))
            self.exit_results(dev=dev, results=dict(
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

    def check_os_install(self, dev):
        profile_dir = os.path.join(self.cli_args.topdir, 'etc', 'profiles', 'default', 'nxos')
        conf_fpath = os.path.join(profile_dir, 'os-selector.cfg')

        cmd = "{topdir}/bin/aztp_os_selector.py -j '{dev_json}' -c {config}".format(
            topdir=self.cli_args.topdir,
            dev_json=json.dumps(dev.facts),
            config=conf_fpath)

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

    def do_os_install(self, dev, image_name):
        vendor_dir = os.path.join(self.cli_args.topdir, 'vendor_images', self.os_name)
        image_fpath = os.path.join(vendor_dir, image_name)

        if not os.path.isfile(image_fpath):
            errmsg = 'image file {} does not exist'.format(image_fpath)
            self.exit_results(dev=dev, results=dict(
                ok=False,
                error_type='install',
                message=errmsg))

        md5sum = self.ensure_md5sum(filepath=image_fpath)
        msg = 'installing OS image [{}] ... please be patient'.format(image_name)
        self.post_device_status(dev=dev, state='OS-INSTALL', message=msg)

        cmd = "nxos-installos --target {target} --server {server} " \
              "-U {u_env} -P {p_env} --image {image} --md5sum {md5sum}".format(
                  target=dev.target, server=self.cli_args.server,
                  u_env=self.cli_args.env_user, p_env=self.cli_args.env_passwd,
                  image=image_name, md5sum=md5sum)

        if self.cli_args.logfile:
            cmd += ' --logfile %s' % self.cli_args.logfile

        child = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
        _stdout, _stderr = child.communicate()
        return json.loads(_stdout)

    def do_ensure_os_version(self, dev):
        os_install = self.check_os_install(dev)

        if not os_install['image']:
            self.log.info('no software install required')
            return dev

        self.log.info('software image install required: %s' % os_install['image'])

        got = self.do_os_install(dev, image_name=os_install['image'])
        if not got['ok']:
            errmsg = 'software install [{ver}] FAILED: {reason}'.format(
                     ver=os_install['image'], reason=json.dumps(got))
            self.log.critical(errmsg)
            self.exit_results(dict(
                ok=False,
                error_type='install',
                message=errmsg))

        self.log.info('software install OK: %s' % json.dumps(got))
        self.log.info('rebooting device ... please be patient')

        self.post_device_status(
            dev, state='REBOOTING',
            message='OS install OK, rebooting ... please be patient')

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
    nxboot = NxosBootstrap(server, cli_args)
    if not os.path.isdir(cli_args.topdir):
        nxboot.exit_results({
            'ok': False,
            'error_type': 'args',
            'message': '{} is not a directory'.format(cli_args.topdir)})

    nxboot.log.info("starting bootstrap process in {} seconds".format(cli_args.init_delay))

    nxboot.post_device_status(
        target=cli_args.target,
        state='START',
        message='bootstrap started, waiting for device access')

    # first wait the init_delay amount of time ... gives the device time
    # to start the shutdown process; i.e. expect this script to be kicked
    # off from the NXOS POAP process.

    time.sleep(cli_args.init_delay)
    dev = nxboot.wait_for_device(countdown=cli_args.reload_delay, poll_delay=10)

    nxboot.log.info("proceeding with bootstrap")
    pretty_facts = "".join(str(key) + ': ' + str(value) + ', ' for key, value in dev.facts.items())
    nxboot.log.info('device facts: {}'.format(pretty_facts))
    nxboot.do_push_config1(dev)
    if dev.facts['virtual']:
        nxboot.log.info('Virtual device. No OS upgrade necessary.')
    else:
        dev = nxboot.do_ensure_os_version(dev)
    nxboot.log.info("bootstrap process finished")
    nxboot.exit_results(dict(ok=True), dev=dev)


if '__main__' == __name__:
    main()
