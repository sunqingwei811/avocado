# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
#
# See LICENSE for more details.
#
# Copyright: Red Hat Inc. 2013-2014
# Author: Ruda Moura <rmoura@redhat.com>

"""
Base Test Runner Plugins.
"""

import sys

from . import plugin
from .. import exit_codes
from .. import output
from .. import job
from .. import multiplexer
from ..settings import settings


class TestRunner(plugin.Plugin):

    """
    Implements the avocado 'run' subcommand
    """

    name = 'test_runner'
    enabled = True
    priority = 0

    def configure(self, parser):
        """
        Add the subparser for the run action.

        :param parser: Main test runner parser.
        """
        self.parser = parser.subcommands.add_parser(
            'run',
            help='Run one or more tests (native test, test alias, binary or script)')

        self.parser.add_argument('url', type=str, default=[], nargs='+',
                                 help='List of test IDs (aliases or paths)')

        self.parser.add_argument('-z', '--archive', action='store_true', default=False,
                                 help='Archive (ZIP) files generated by tests')

        self.parser.add_argument('--force-job-id', dest='unique_job_id',
                                 type=str, default=None,
                                 help=('Forces the use of a particular job ID. Used '
                                       'internally when interacting with an avocado '
                                       'server. You should not use this option '
                                       'unless you know exactly what you\'re doing'))

        self.parser.add_argument('--job-results-dir', action='store',
                                 dest='logdir', default=None, metavar='DIRECTORY',
                                 help=('Forces to use of an alternate job '
                                       'results directory.'))

        self.parser.add_argument('--job-timeout', action='store',
                                 default=None, metavar='SECONDS',
                                 help=('Set the maximum amount of time (in SECONDS) that '
                                       'tests are allowed to execute. '
                                       'Note that zero means "no timeout". '
                                       'You can also use suffixes, like: '
                                       ' s (seconds), m (minutes), h (hours). '))

        sysinfo_default = settings.get_value('sysinfo.collect',
                                             'enabled',
                                             key_type='bool',
                                             default=True)
        sysinfo_default = 'on' if sysinfo_default is True else 'off'
        self.parser.add_argument('--sysinfo', choices=('on', 'off'), default=sysinfo_default,
                                 help=('Enable or disable system information '
                                       '(hardware details, profilers, etc.). '
                                       'Current:  %(default)s'))

        self.parser.output = self.parser.add_argument_group('output and result format')

        self.parser.output.add_argument(
            '-s', '--silent', action='store_true', default=False,
            help='Silence stdout')

        self.parser.output.add_argument(
            '--show-job-log', action='store_true', default=False,
            help=('Display only the job log on stdout. Useful '
                  'for test debugging purposes. No output will '
                  'be displayed if you also specify --silent'))

        out_check = self.parser.add_argument_group('output check arguments')

        out_check.add_argument('--output-check-record',
                               choices=('none', 'all', 'stdout', 'stderr'),
                               default='none',
                               help=('Record output streams of your tests '
                                     'to reference files (valid options: '
                                     'none (do not record output streams), '
                                     'all (record both stdout and stderr), '
                                     'stdout (record only stderr), '
                                     'stderr (record only stderr). '
                                     'Current: %(default)s'))

        out_check.add_argument('--output-check', choices=('on', 'off'),
                               default='on',
                               help=('Enable or disable test output (stdout/stderr) check. '
                                     'If this option is off, no output will '
                                     'be checked, even if there are reference files '
                                     'present for the test. '
                                     'Current: on (output check enabled)'))

        if multiplexer.MULTIPLEX_CAPABLE:
            mux = self.parser.add_argument_group('multiplexer use on test execution')
            mux.add_argument('-m', '--multiplex-files', nargs='*',
                             default=None, metavar='FILE',
                             help='Location of one or more Avocado multiplex (.yaml) '
                             'FILE(s) (order dependent)')
            mux.add_argument('--filter-only', nargs='*', default=[],
                             help='Filter only path(s) from multiplexing')
            mux.add_argument('--filter-out', nargs='*', default=[],
                             help='Filter out path(s) from multiplexing')
            mux.add_argument('--mux-path', nargs='*', default=None,
                             help="List of paths used to determine path "
                             "priority when querying for parameters")
            mux.add_argument('--mux-inject', default=[], nargs='*',
                             help="Inject [path:]key:node values into the "
                             "final multiplex tree.")
        super(TestRunner, self).configure(self.parser)
        # Export the test runner parser back to the main parser
        parser.runner = self.parser

    def activate(self, args):
        # Extend default multiplex tree of --mux_inject values
        for value in getattr(args, "mux_inject", []):
            value = value.split(':', 2)
            if len(value) < 2:
                raise ValueError("key:value pairs required, found only %s"
                                 % (value))
            elif len(value) == 2:
                args.default_multiplex_tree.value[value[0]] = value[1]
            else:
                node = args.default_multiplex_tree.get_node(value[0], True)
                node.value[value[1]] = value[2]

    def _validate_job_timeout(self, raw_timeout):
        units = {'s': 1, 'm': 60, 'h': 3600, 'd': 86400}
        mult = 1
        if raw_timeout is not None:
            try:
                unit = raw_timeout[-1].lower()
                if unit in units:
                    mult = units[unit]
                    timeout = int(raw_timeout[:-1]) * mult
                else:
                    timeout = int(raw_timeout)
                if timeout < 1:
                    raise ValueError()
            except (ValueError, TypeError):
                self.view.notify(
                    event='error',
                    msg=("Invalid number '%s' for job timeout. "
                         "Use an integer number greater than 0") % raw_timeout)
                sys.exit(exit_codes.AVOCADO_FAIL)
        else:
            timeout = 0
        return timeout

    def run(self, args):
        """
        Run test modules or simple tests.

        :param args: Command line args received from the run subparser.
        """
        self.view = output.View(app_args=args)
        if args.unique_job_id is not None:
            try:
                int(args.unique_job_id, 16)
                if len(args.unique_job_id) != 40:
                    raise ValueError
            except ValueError:
                self.view.notify(event='error', msg='Unique Job ID needs to be a 40 digit hex number')
                sys.exit(exit_codes.AVOCADO_FAIL)
        args.job_timeout = self._validate_job_timeout(args.job_timeout)
        job_instance = job.Job(args)
        return job_instance.run()
