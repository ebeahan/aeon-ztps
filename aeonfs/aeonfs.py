from __future__ import print_function, absolute_import, division

import logging
import os, pwd, grp
import errno
import sys

from hiyapyco import odyldo as ody
from collections import OrderedDict

from collections import defaultdict
from errno import *
from stat import *
from time import time


from aeondb import *
from aeonutil import *

import hiyapyco as yml

from sqlalchemy import create_engine
from sqlalchemy.inspection import inspect
from sqlalchemy.orm import sessionmaker

from fuse import FUSE, FuseOSError, Operations, LoggingMixIn, fuse_get_context

AEON_RESERVED_DIRECTORIES = ["/", "/aeondb"]

class AeonFS(LoggingMixIn, Operations):


    ## Initialize
    def __init__(self, cfg):

        self.cfg = cfg
        self.fh = 100000
        self.open_paths = dict()
        self.open_fhs = dict()
        self.engine = create_engine(self.cfg["engine"])
        Session = sessionmaker(bind=self.engine)
        self.sas = Session()
        AeonBase.metadata.create_all(self.engine)

        user = pwd.getpwnam("aeon")
        self.username = "aeon"
        self.uid = user[2]
        self.gid = user[3]

        if not self.path_exists("/"):
            now = time()
            mode = (S_IFDIR | 0o666)
            self.root = AeonFile(mode = mode, nlink = 2, uid = self.uid, gid = self.gid, ctime = now, mtime = now, atime = now, path = "/", ftype = AeonFileTypes.DIRECTORY)
            self.sas.add(self.root)
            self.sas.commit()

            rootobj = self.sas.query(AeonFile).filter(AeonFile.path == "/").one()

            self.metadir = AeonFile(dirid = rootobj.fid, mode = mode, nlink = 2, uid = self.uid, gid = self.gid, ctime = now, atime = now, mtime = now, path = "/aeondb", ftype = AeonFileTypes.DIRECTORY)
            self.sas.add(self.root)
            self.sas.commit()




    ## Helper routines

    def parse_flags(self, flags):

        res = dict()


        for osflag, name in OS_FLAGS.items():

            if (osflag & flags) == osflag:
                res[name] = True
            else:
                res[name] = False


        return res

    def get_fh(self):

        self.fh += 1

        return self.fh


    def aeon_open_file(self, fc, afile, mode, flags):

        if afile.path not in self.open_paths:

            self.open_paths[afile.path] = dict()
            self.open_paths[afile.path]["fd"] = dict()
            self.open_paths[afile.path]["lock"] = {"locked": False,
                                                   "fh"    : None}


        newflags = self.parse_flags(flags)

        fh = self.get_fh()

        if (newflags["wo"] or newflags["rw"]):
            if self.open_paths[afile.path]["lock"]["locked"]:
                raise FuseOSError(EWOULDBLOCK)
            else:
                self.open_paths[afile.path]["lock"]["locked"] = True
                self.open_paths[afile.path]["lock"]["fh"] = fh

        self.open_paths[afile.path]["fd"]["fh"] = fh
        self.open_paths[afile.path]["fd"]["flags"] = newflags
        self.open_paths[afile.path]["fd"]["context"] = fc







    def path_exists(self, path):

        q = self.sas.query(AeonFile).filter(AeonFile.path == path)
        return self.sas.query(q.exists()).scalar()

    def yaml_to_schema(self, ys):

        sod = ody.safe_load(ys)

        ## Create new AeonDB table

        tname = sod["name"]
        nst = AeonTable(name=tname)
        self.sas.add(nst)
        cols = dict()

        ## Create AeonDB columns, add them to the table

        for colname in sod["columns"]:

            coltype = sod["columns"][colname]["type"]
            length = sod["columns"][colname]["length"]
            autoinc = sod["columns"][colname]["autoincrement"]

            nsc = AeonColumn(name=colname, coltype=coltype, length=length, autoincrement=autoinc)

            self.sas.add(nsc)
            nst.columns.append(nsc)

            cols["colname"] = nsc

        ## Create AeonDB args, add columns to them, and add the args to the table

        for argname in sod["args"]:

            argtype = sod["args"][argname]["type"]
            argcols = sod["args"][argname]["columns"]

            nsa = AeonArg(name=argname, argtype=argtype)
            self.sas.add(nsa)

            for ac in argcols:
                nsa.columns.append(cols[ac])

            nst.args.append(nsa)


        ##  Commit

        self.sas.commit()

    def schema_to_ordereddict(self, tabid):

        res = OrderedDict()

        ## Get table name:

        tbl = self.sas.query(AeonTable).filter(AeonTable.tabid == tabid).one()
        res["name"] = tbl.name

        ## Get column names and attributes:

        res["columns"] = OrderedDict()

        for col in tbl.columns:
            res["columns"][col.name] = OrderedDict()
            res["columns"][col.name]["type"] = col.coltype
            res["columns"][col.name]["length"] = col.length
            res["columns"][col.name]["autoincrement"] = col.autoincrement

        ## Get args:

        for arg in tbl.args:
            res["args"][arg.name] = OrderedDict()
            res["args"][arg.name]["type"] = arg.argtype
            res["args"][arg.name]["columns"] = []

            for ac in arg.columns:
                res["args"][arg.name]["columns"].append(ac.name)

        ## Get columns in each constraint:

        return res

    def schema_to_yaml(self, tabid):

        return ody.safe_dump(self.schema_to_ordereddict(tabid))

    ## Attribute related Operations

    def access(self, path, mode):
        pass

    def chmod(self, path, mode):
        pass


    def chown(self, path, uid, gid):
        pass

    def getattr(self, path, fh=None):


        if self.path_exists(path):
            attrs = dict()
            attrs["st_size"] = 0

            fsobj = self.sas.query(AeonFile).filter(AeonFile.path == path).one()

            attrs["st_mode"] = fsobj.mode
            attrs["st_uid"] = fsobj.uid
            attrs["st_gid"] = fsobj.gid
            attrs["st_nlink"] = fsobj.nlink
            attrs["st_ctime"] = fsobj.ctime
            attrs["st_mtime"] = fsobj.mtime
            attrs["st_atime"] = fsobj.atime

            return attrs
        else:
            raise FuseOSError(ENOENT)

    def statfs(self, path):
        pass

    def utimens(self, path, times=None):
        pass

    ## Directory related Operations

    def readdir(self, path, fh):

        dirents = ['.', '..']

        if self.path_exists(path):
            fsobj = self.sas.query(AeonFile).filter(AeonFile.path == path).one()

            if fsobj.ftype == AeonFileTypes.DIRECTORY:
                dirlist = self.sas.query(AeonFile).filter(AeonFile.dirid == fsobj.fid)

                for d in dirlist:
                    dirents.append(d.name)

                return dirents
            else:
                raise FuseOSError(ENOTDIR)
        else:
            raise FuseOSError(ENOENT)

    def rmdir(self, path):

        if path in AEON_RESERVED_DIRECTORIES:
            raise FuseOSError(EPERM)

        if self.path_exists(path):
            fsobj = self.sas.query(AeonFile).filter(AeonFile.path == path).one()



            if fsobj.ftype == AeonFileTypes.DIRECTORY:
                q = self.sas.query(AeonFile).filter(AeonFile.dirid == fsobj.fid)
                not_empty = self.sas.query(q.exists()).scalar()

                if not_empty:
                    raise FuseOSError(ENOTEMPTY)
                else:
                    dirobj = self.sas.query(AeonFile).filter(AeonFile.fid == fsobj.dirid).one()
                    self.sas.delete(fsobj)
                    dirobj.nlink -= 1
                    self.sas.commit()
                    return 0
            else:
                raise FuseOSError(ENOTDIR)

        else:
            raise FuseOSError(ENOENT)

    def mkdir(self, path, mode):

        fc = fuse_get_context()

        if self.path_exists(path):
            raise FuseOSError(EEXIST)

        (filepath, filename) = os.path.split(path)

        dirobj = self.sas.query(AeonFile).filter(AeonFile.path == filepath).one()

        now  = time()
        newdir = AeonFile(dirid = dirobj.fid,
                          mode = (S_IFDIR | mode),
                          uid = fc[2],
                          gid = fc[3],
                          ftype = AeonFileTypes.DIRECTORY,
                          nlink = 2,
                          ctime = now,
                          mtime = now,
                          atime = now,
                          path = path,
                          name = filename)

        self.sas.add(newdir)
        dirobj.nlink += 1
        self.sas.commit()

        return 0

    ## File related Operations


    def open(self, path, flags):
        pass


    def create(self, path, mode, fi=None):

        fc = fuse_get_context()

        if self.path_exists(path):
            raise FuseOSError(EEXIST)

        (filepath, filename) = os.path.split(path)

        dirobj = self.sas.query(AeonFile).filter(AeonFile.path == filepath).one()

        now = time()

        newfile = AeonFile(dirid = dirobj.fid,
                           mode = (S_IFREG | mode),
                           uid = fc[0],
                           gid = fc[1],
                           nlink = 1,
                           ctime = now,
                           mtime = now,
                           atime = now,
                           ftype = AeonFileTypes.REGULAR,
                           path = path,
                           name = filename)

        self.sas.add(newfile)
        self.sas.commit()

        return self.aeon_open_file(fc, newfile, (os.CREAT | os.O_WRONLY | os.O_TRUNC))






    def read(self, path, length, offset, fh):
        pass


    def write(self, path, buf, offset, fh):
        pass

    def truncate(self, path, length, fh=None):
        pass


    def flush(self, path, fh):
        pass


    def release(self, path, fh):
        pass


    def fsync(self, path, fdatasync, fh):
        pass



if __name__ == '__main__':

    ## Load Config
    cfg = yml.load("aeoncfg.yaml")

    ## Connect to database
    FUSE(AeonFS(cfg), cfg["mountpoint"], nothreads=True, foreground=True)

