from sqlalchemy import MetaData, Column, Integer, String, Boolean, LargeBinary, Enum
from sqlalchemy import PrimaryKeyConstraint, ForeignKeyConstraint, UniqueConstraint, Index
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base

import enum
from hiyapyco import odyldo as ody
from collections import OrderedDict

aeon_naming_convention = {
  "ix": 'ix_%(column_0_label)s',
  "uq": "uq_%(table_name)s_%(column_0_name)s",
  "ck": "ck_%(table_name)s_%(constraint_name)s",
  "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
  "pk": "pk_%(table_name)s"
}

aeonmd = MetaData(naming_convention=aeon_naming_convention)
AeonBase = declarative_base(metadata=aeonmd)

# The following classes define Aeon schema elements and enumerations

class AeonColumnTypes(object):

    BOOLEAN = 1
    INTEGER = 2
    STRING = 3

class AeonArgTypes(object):

    PRIMARYKEY = 1
    UNIQUE = 2
    INDEX = 3
    FOREIGNKEY = 4

class AeonTable(AeonBase):

    __tablename__ = "aeontables"
    __table_args__ = (PrimaryKeyConstraint("tabid"),)

    tabid = Column(Integer)
    name = Column(String(64))
    columns = relationship("AeonColumn", backref = "table")
    args = relationship("AeonArg", backref = "table")

class AeonColumn(AeonBase):

    __tablename__ = "aeoncolumns"
    __table_args__ = (PrimaryKeyConstraint("colid"),
                      ForeignKeyConstraint(["tabid"], ["aeontables.tabid"]))

    colid = Column(Integer)
    tabid = Column(Integer)
    coltype = Column(Integer)
    length = Column(Integer)
    autoincrement = Column(Boolean)
    name = Column(String(64))
    args = relationship("AeonArgMap", backref = "column")

class AeonArg(AeonBase):


    __tablename__ = "aeonargs"
    __table_args__ = (PrimaryKeyConstraint("argid"),
                      ForeignKeyConstraint(["tabid"], ["aeontables.tabid"]))

    argid = Column(Integer)
    tabid = Column(Integer)
    argtype = Column(Integer)
    name = Column(String(64))
    columns = relationship("AeonArgMap", backref = "arg")

class AeonArgMap(AeonBase):

    __tablename__ = "aeonargmaps"
    __table_args__ = (PrimaryKeyConstraint("argid", "colid"),
                      ForeignKeyConstraint(["argid"], ["aeonargs.argid"]),
                      ForeignKeyConstraint(["colid"], ["aeoncolumns.colid"]))

    argid = Column(Integer)
    colid = Column(Integer)


# The following classes define Aeon filesystem objects

class AeonFileTypes(object):

    SCHEMA = 1
    RECORD = 2
    DIRECTORY = 3
    REGULAR = 4
    SYMLINK = 5

class AeonFile(AeonBase):

    __tablename__ = "aeonfiles"
    __table_args__ = (PrimaryKeyConstraint("fid"),
                      UniqueConstraint("path"),
                      Index("ix_path", "path"))

    fid = Column(Integer)
    dirid = Column(Integer)
    mode = Column(Integer)
    uid = Column(Integer)
    gid = Column(Integer)
    nlink = Column(Integer)
    ctime = Column(Integer)
    mtime = Column(Integer)
    atime = Column(Integer)
    ftype = Column(Integer)
    tid = Column(Integer)
    path = Column(String(1024))
    name = Column(String(64))
    blob = Column(LargeBinary)





