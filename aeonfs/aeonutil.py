import pwd, grp
import os
import stat

SUPPORTED_FILE_TYPES = (stat.S_IFDIR | stat.S_IFREG | stat.S_IFLNK)

OPEN_WRITE_FLAGS = (os.O_WRONLY | os.O_RDWR)

OPEN_READ_FLAGS = (os.O_RDONLY | os.O_RDWR)

MODE_FLAGS = {
               stat.S_IFDIR : "dir",
               stat.S_IFREG : "reg",
               stat.S_IFLNK : "lnk",
               stat.S_IRUSR : "ur",
               stat.S_IWUSR : "uw",
               stat.S_IXUSR : "ux",
               stat.S_IRGRP : "gr",
               stat.S_IWGRP : "gw",
               stat.S_IXGRP : "gx",
               stat.S_IROTH : "or",
               stat.S_IWOTH : "ow",
               stat.S_IXOTH : "ox"}

OS_FLAGS = {
             os.O_RDONLY    : "ro",
             os.O_WRONLY    : "wo",
             os.O_RDWR      : "rw",
             os.O_APPEND    : "a",
             os.O_CREAT     : "c",
             os.O_EXCL      : "e",
             os.O_TRUNC     : "t",
             os.O_DSYNC     : "ds",
             os.O_RSYNC     : "rs",
             os.O_SYNC      : "s",
             os.O_NDELAY    : "nd",
             os.O_NONBLOCK  : "nb",
             os.O_NOCTTY    : "nc",
             os.O_ASYNC     : "as",
             os.O_DIRECT    : "d",
             os.O_DIRECTORY : "dir",
             os.O_NOFOLLOW  : "nf",
             os.O_NOATIME   : "na"
           }

def aeon_operation_permitted(context, file_user, file_group, mode, flags):

    pass


class AeonFileAttribute(object):

    def __init__(self):
        pass

class AeonContext(object):

    def __init__(self, fc):

        user = pwd.getpwuid(fc[0])
        group = grp.getgrgid(fc[1])

        ugids = set()
        ugroups = set()

        ugids.add(user[3])

        ugroup = grp.getgrgid(user[3])
        ugroups.add(ugroup[0])

        allgroups = grp.getgrall()

        for g in allgroups:
            if user[0] in g[3]:
                ugids.add(g[2])
                ugroups.add(g[0])

        self.username = user[0]
        self.user_all_group_names = ugroups
        self.user_all_gids = ugids
        self.uid = fc[0]
        self.gid = fc[1]
        self.pid = fc[2]

class BitFlag(object):

    def __init__(self, flag_constants, flag_bits):

        for flag_constant, field in flag_constants.items():

            if (flag_constant & flag_bits) == flag_constant:

                setattr(self, field, True)

            else:

                setattr(self, field, False)
