# Copyright 2014-present, Apstra, Inc. All rights reserved.
#
# This source code is licensed under End User License Agreement found in the
# LICENSE file at http://www.apstra.com/community/eula

#
#  Copyright 2016-present, Apstra, Inc.  All rights reserved.
#
#  This source code is licensed under Community End User License Agreement
#  found in the LICENSE.txt file in the root directory of this source tree.
#

from setuptools import setup, find_packages
from setuptools.command.test import test as TestCommand
import sys

# parse requirements
req_lines = [line.strip() for line in open(
    'requirements.txt').readlines()]
install_reqs = list(filter(None, req_lines))

class Tox(TestCommand):
    def finalize_options(self):
        TestCommand.finalize_options(self)
        self.test_args = []
        self.test_suite = True
    def run_tests(self):
        import tox
        errcode = tox.cmdline(self.test_args)
        sys.exit(errcode)

setup(
    name="aeon-ztp",
    version="1.1.0",
    author="Apstra Customer Enablement",
    author_email="community@apstra.com",
    description=("AEON ZTP Server"),
    url="https://github.com/Apstra/aeon-ztps",
    scripts=['aeon_ztp/bin/aztp-db-flush'],
    license="Apache 2.0",
    keywords="networking automation vendor-agnostic",
    packages=find_packages(exclude=["tests", ".*"]),
    include_package_data=True,
    install_requires=install_reqs,
    zip_safe=False,
    tests_require=['tox'],
    cmdclass = {'test': Tox},
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Intended Audience :: Developers',
        'Intended Audience :: Information Technology',
        'Intended Audience :: System Administrators',
        'Intended Audience :: Telecommunications Industry',
        'License :: OSI Approved :: Apache Software License',
        'Operating System :: POSIX :: Linux',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2.7',
        'Topic :: Software Development :: Libraries',
        'Topic :: Software Development :: Libraries :: Application Frameworks',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'Topic :: System :: Networking',
    ],
)
