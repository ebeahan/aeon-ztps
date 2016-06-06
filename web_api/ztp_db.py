from sqlalchemy import Column, ForeignKey, Integer, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from marshmallow_sqlalchemy import ModelSchema

__all__ = [
    'Device',
    'get_session'
]

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
    last_update = Column(String(64), nullable=False)

class DeviceSchema(ModelSchema):
    class Meta:
        model = Device

Device.Schema = DeviceSchema


def get_session():
    DBSession = sessionmaker(bind=engine)
    return DBSession()


engine = create_engine('sqlite:///aeon-ztp.db')
Base.metadata.create_all(engine)
