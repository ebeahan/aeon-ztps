# Copyright 2014-present, Apstra, Inc. All rights reserved.
#
# This source code is licensed under End User License Agreement found in the
# LICENSE file at http://www.apstra.com/community/eula

from aeon_ztp import db, ma


class Device(db.Model):
    Schema = None
    __tablename__ = 'devices'

    ip_addr = db.Column(db.String(16), primary_key=True)
    os_name = db.Column(db.String(16), nullable=False)
    serial_number = db.Column(db.String(64))
    hw_model = db.Column(db.String(64))
    os_version = db.Column(db.String(64))
    state = db.Column(db.String(64))
    message = db.Column(db.String(10000))
    created_at = db.Column(db.DateTime(), nullable=False)
    updated_at = db.Column(db.DateTime(), nullable=False)
    facts = db.Column(db.String(2000))
    finally_script = db.Column(db.String(256))
    image_name = db.Column(db.String(256))


class DeviceSchema(ma.ModelSchema):
    class Meta:
        model = Device


device_schema = DeviceSchema()
