#!/usr/bin/env python

from subprocess import Popen, PIPE
import re

run_args = [
    'aztp-oschk',
    '--os_ver %s' % re.escape('7.0(3)I1(1b)'),
    '--hw_model %s' % re.escape('N9K-9332PQ')]

# must pass command as a single string; using shell=True

this = Popen(' '.join(run_args), shell=True,
             stdout=PIPE, stderr=PIPE)

rc = this.returncode
_stdout, _stderr = this.communicate()
