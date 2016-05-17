#
#  Copyright 2016-present, Apstra, Inc.  All rights reserved.
#
#  This source code is licensed under Community End User License Agreement
#  found in the LICENSE.txt file in the root directory of this source tree.
#

from setuptools import setup, find_packages
from glob import glob

# parse requirements
req_lines = [line.strip() for line in open(
    'requirements.txt').readlines()]
install_reqs = list(filter(None, req_lines))

libdir = 'pylib'
packages = find_packages(libdir)

setup(
    name="aeon-ztp",
    namespace_packages=['aeon'],
    version="0.0.1",
    author="Jeremy Schulman",
    author_email="jeremy@apstra.com",
    description=("AEON ZTP Server"),
    license="Apache 2.0",
    keywords="networking automation vendor-agnostic",
    package_dir={'': libdir},
    packages=packages,
    install_requires=install_reqs,
    data_files=[
        ('images', glob('images/*'))
    ],
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'Intended Audience :: Information Technology',
        'Intended Audience :: System Administrators',
        'Intended Audience :: Telecommunications Industry',
        'License :: OSI Approved :: Apache Software License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2.7',
        'Topic :: Software Development :: Libraries',
        'Topic :: Software Development :: Libraries :: Application Frameworks',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'Topic :: System :: Networking',
    ],
)
