#!/usr/bin/env python

import sys
import json
import argparse
import yaml
import re
import operator
from collections import namedtuple
from yaml.scanner import ScannerError

_PROGNAME = 'aztp_os_selector'


class HwNoMatchError(Exception):
    pass


class HwMultiMatchError(Exception):
    pass


class CfgError(Exception):
    pass


class ArgumentParser(argparse.ArgumentParser):
    class ParserError(Exception):
        pass

    def error(self, message):
        raise ArgumentParser.ParserError(message)


def cli_parse(cmdargs=None):
    psr = ArgumentParser(
        prog=_PROGNAME,
        description="Aeon ZTP network OS selector",
        add_help=True)

    psr.add_argument(
        '-c', '--config',
        dest='config_file',
        help='configuration file',
        default='os-selector.cfg')

    psr.add_argument(
        '-j', '--json', required=True,
        help='Device data in JSON format'
    )

    # any error with args parsing will raise an exception;
    # this will be caught in the calling environment and
    # handled properly

    return psr.parse_args(cmdargs)

# ##### -----------------------------------------------------------------------
# #####
# #####                           Utility Functions
# #####
# ##### -----------------------------------------------------------------------


def exit_results(results, exit_error=None):
    json.dump(results, fp=sys.stdout)
    sys.exit(0 if results['ok'] else exit_error or 1)


def load_cfg(filepath):
    try:
        return yaml.safe_load(open(filepath))
    except (IOError, ScannerError) as e:
        if isinstance(e, IOError):
            exit_results({
                'ok': False,
                'error_type': 'args',
                'error_message': 'Unable to load file: %s' % filepath
            })
        else:
            exit_results({
                'ok': False,
                'error_type': 'args',
                'error_message': 'YAML syntax error in file: {filepath}, {e}'.format(filepath=filepath, e=e)
            })


def match_hw_model(dev_data, cfg_data):
    # find entry matching the hw_model
    item_match = namedtuple('item_match', ['hw_match', 'data'])

    matches = []

    for group in cfg_data.iteritems():
        if group[0] != 'default':
            for fact_key, fact_value in group[1]['matches'].iteritems():
                if dev_data[fact_key] not in str(fact_value):
                    # Stop checking this device group if any of the matches don't match
                    break
            else:
                # If all matches in match group match, return item_match
                matches.append(group[0])

    # validate on the number of matches found

    n_found = len(matches)
    if 0 == n_found:
        if 'default' in cfg_data:
            return item_match('default', cfg_data['default'])
        else:
            raise HwNoMatchError()
    elif n_found > 1:
        raise HwMultiMatchError(
            'matches multiple os-selector groups: {}'
            .format(matches)
        )

    return item_match(matches[0], cfg_data[matches[0]])


def match_os_version(dev_data, hw_match):
    """
    Examines the matched hw_model entry and compares
    the expected vs. actual OS versions.  If the actual OS
    version does match the Users intent, then return the
    image name for the system to load.  Otherwise return None.
    """
    os_ver = dev_data['os_version'].lower()
    _keys = ['exact_match', 'regex_match']
    if not any(k in hw_match for k in _keys):
        raise CfgError(
            'Expecting one of: {}'
            .format(_keys))

    # if the User specifies a regex match, then check for
    # that match; ignoring case

    match = hw_match.get('regex_match')
    if match:
        found = re.match(pattern=match, string=os_ver,
                         flags=re.IGNORECASE)
        return False if found else hw_match['image']

    # 'listify' the exact value and then check the actual os
    # version against one of the one's specified by the User.
    # make the values lower-case to ignore case

    exact = hw_match.get('exact_match')
    exact = exact if isinstance(exact, list) else [exact]
    found = any(operator.eq(os_ver, this.lower()) for this in exact)
    return False if found else hw_match['image']


def main():
    try:

        cli_args = cli_parse()
        cfg_data = load_cfg(cli_args.config_file)
        try:
            dev_data = json.loads(cli_args.json)
            hw_match = match_hw_model(dev_data, cfg_data)
            sw_match = match_os_version(dev_data, hw_match.data)
            finally_script = hw_match.data.get('finally')

        except ValueError:
            exit_results({
                'ok': False,
                'error_type': 'args',
                'error_message': 'JSON argument formatted incorrectly.'
            })

    except ArgumentParser.ParserError as exc:
        exit_results({
            'ok': False,
            'error_type': 'args',
            'error_message': exc.message
        })

    except HwNoMatchError:
        exit_results({
            'ok': False,
            'error_type': 'hw_match',
            'error_message': 'no matching hw_model value'
        })

    except HwMultiMatchError as exc:
        exit_results({
            'ok': False,
            'error_type': 'hw_match',
            'error_message': exc.message
        })

    except CfgError as exc:
        exit_results({
            'ok': False,
            'error_type': 'cfg_error',
            'error_message': exc.message
        })

    exit_results({
        'ok': True,
        'image_name': sw_match,
        'finally': finally_script
    })


if __name__ == '__main__':
    main()
