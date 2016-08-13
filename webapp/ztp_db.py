# Copyright 2014-present, Apstra, Inc. All rights reserved.
#
# This source code is licensed under End User License Agreement found in the
# LICENSE file at http://www.apstra.com/community/eula

import os
from sqlalchemy import Column, ForeignKey, Integer, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from marshmallow_sqlalchemy import ModelSchema

__all__ = [
    'Device',
    'get_session'
]

_AEON_TOPDIR = os.getenv('AEON_TOPDIR')

Base = declarative_base()

class Device(Base):
    Schema = None
    __tablename__ = 'devices'

    ip_addr = Column(String(16), primary_key=True)
    os_name = Column(String(16), nullable=False)
    serial_number = Column(String(32))
    hw_model = Column(String(24))
    os_version = Column(String(32))
    state = Column(String(15))
    message = Column(String(128))
    created_at = Column(String(64), nullable=False)
    updated_at = Column(String(64), nullable=False)


class DeviceSchema(ModelSchema):
    class Meta:
        model = Device

Device.Schema = DeviceSchema


def get_session():
    DBSession = sessionmaker(bind=engine)
    return DBSession()


engine = create_engine('sqlite:///{topdir}/run/aeon-ztp.db'.format(topdir=_AEON_TOPDIR))
Base.metadata.create_all(engine)
