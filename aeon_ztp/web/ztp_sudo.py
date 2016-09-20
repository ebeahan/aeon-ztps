import subprocess
import pwd
import os
_dhcp_leases_file = '/var/lib/dhcp/dhcpd.leases'


def run(cmd):
    """ Runs a command through sudo.  Expects sudoers to permit this as the user invoking command is running as.

    Examples:
      run("/usr/bin/sudo /bin/systemctl restart isc-dhcp-server")

    :param cmd:
    :return:
    """
    try:
        p = subprocess.Popen(cmd.split(),
                         stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE
                             )
        out, err = p.communicate()
        if err:
            raise OSError('{err} {out}'.format(out=out, err=err))
        return out
    except subprocess.CalledProcessError as e:
        print e
        raise
    except:
        raise


def sudo(cmd):
    whoami = pwd.getpwuid(os.getuid())[0]

    try:
        run("/usr/bin/sudo -n {cmd}".format(cmd=cmd))
    except OSError:
        raise OSError("{whoami} is not permitted to sudo {cmd}".format(whoami=whoami, cmd=cmd))
    return run("/usr/bin/sudo {cmd}".format(cmd=cmd))


def flush_dhcp():
    # test code
    try:
        return sudo("/usr/local/bin/dhcpd-reset")
        # sudo("/bin/systemctl restart isc-dhcp-server")
    except OSError as e:
        return False, '{}'.format(e)


def aosetc_import():
    # test code
    try:
        return sudo("/opt/aosetc/bin/aeon-ztp")
        # sudo("/bin/systemctl restart isc-dhcp-server")
    except OSError as e:
        return False, '{}'.format(e)
