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
    serial_number = Column(String(32), primary_key=True)
    ip_addr = Column(String(16), nullable=False)
    hw_model = Column(String(24), nullable=False)
    os_version = Column(String(32), nullable=False)
    os_name = Column(String(16), nullable=False)

class DeviceSchema(ModelSchema):
    class Meta:
        model = Device

Device.Schema = DeviceSchema

def get_session():
    DBSession = sessionmaker(bind=engine)
    return DBSession()


engine = create_engine('sqlite:///aeon-ztp.db')
Base.metadata.create_all(engine)
