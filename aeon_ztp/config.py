# Copyright 2014-present, Apstra, Inc. All rights reserved.
#
# This source code is licensed under End User License Agreement found in the
# LICENSE file at http://www.apstra.com/community/eula
import os
_AEON_TOPDIR = os.getenv('AEON_TOPDIR')
if not _AEON_TOPDIR:
    _AEON_TOPDIR = os.getcwd()


class Config(object):
    CELERY_BROKER_URL = 'amqp://'
    CELERY_RESULT_BACKEND = 'rpc://'
    SECRET_KEY = 'AHJFauf2wUAWFJAwfhyawfhAWFUHJAWEUFOawefuaWEFUWAEFUAWEFahfaF43*3'
    SQLALCHEMY_TRACK_MODIFICATIONS = False


class ProductionConfig(Config):
    DEBUG = False
    TESTING = False
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///' + os.path.join(_AEON_TOPDIR, 'run/data.sqlite')


class DevelopmentConfig(Config):
    DEBUG = True
    TESTING = False
    SQLALCHEMY_DATABASE_URI = os.environ.get('DEV_DATABASE_URL') or \
        'sqlite:///' + os.path.join(_AEON_TOPDIR, 'run/data-dev.sqlite')


class TestingConfig(Config):
    DEBUG = False
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite://'


config = {
    "production": ProductionConfig,
    "testing": TestingConfig,
    "development": DevelopmentConfig,

    "default": DevelopmentConfig
}
