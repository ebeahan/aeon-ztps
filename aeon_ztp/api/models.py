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
    serial_number = db.Column(db.String(32))
    hw_model = db.Column(db.String(24))
    os_version = db.Column(db.String(32))
    state = db.Column(db.String(15))
    message = db.Column(db.String(128))
    created_at = db.Column(db.String(64), nullable=False)
    updated_at = db.Column(db.String(64), nullable=False)
    facts = db.Column(db.String(2000))
    finally_script = db.Column(db.String(256))
    image_name = db.Column(db.String(256))


class DeviceSchema(ma.ModelSchema):
    class Meta:
        model = Device


device_schema = DeviceSchema()
