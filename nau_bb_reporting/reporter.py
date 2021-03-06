"""
Run using:

python3 reporter.py --config config.ini [--term {termcode}] {report-name}

Only one report will be run per invocation. If multiple reports are listed,
behavior is undefined. If no term is passed to a term-specific report, the
report will be either run against all terms (can be VERY time-consuming on most of
the reports) or will error out if it's too tailored to specific terms.

A single Excel spreadsheet will be written to the report directory specified
in the config file. See configuration example file for documentation of
config parameters.

Extending this tool with more reports should be kinda not really painless.
It's pretty straightforward, but just to be sure, this is how the current
reports were all added:

1) Add a new report name to the options in housekeeping.py
2) Add a conditional below to check report == 'new_report_name'
3) Inside conditional, define a report path, and any configuration options. Any config options
    need to be added to the config file and parsed appropriately.
4) Add a new file to the reports package
5) Copy one of the simpler reports and replace queries and processing as needed.
    Use pandas to create a DataFrame from the list of tuples or dicts, and write to excel.
6) Import that report file here, and add a run command in the appropriate conditional.

See? Not hard at all.
"""

__author__ = 'adam'

import configparser
import os
import logging
import re
import time

import cx_Oracle

import nau_bb_reporting.ssh_tunnel as ssh
import nau_bb_reporting.housekeeping as housekeeping
import nau_bb_reporting.reports.stale_courses as stale_courses
import nau_bb_reporting.reports.force_completion as force_completion
import nau_bb_reporting.reports.hardlinks as hardlinks
import nau_bb_reporting.reports.mediafiles as mediafiles
import nau_bb_reporting.reports.orphanedinternal as orphanedinternal



# parse arguments
args = housekeeping.parse_cli_arguments()

# read configuration
config = configparser.ConfigParser()

config.read(args['config'])
log_file = config['LOG'].get('file', 'nau-bb-reporting.log')

# setup root logger
housekeeping.create_root_logger(log_file)
log = logging.getLogger('nau_bb_reporting.reporter')
log.debug("Parameters: %s", args)

# remaining configuration
report_directory = config['PATHS']['report_dir'] + os.sep

db_conf = config['OPENDB']
db_host = db_conf['host']
db_port = int(db_conf['port'])
db_user = db_conf['user']
db_pass = db_conf['pass']

ssh_conf = config['SSH PROXY']
ssh_host = ssh_conf['host']
ssh_port = int(ssh_conf.get('port', 22))
local_port = int(ssh_conf.get('local_port', 1521))
ssh_user = ssh_conf['user']
ssh_pass = ssh_conf['pass']

# validate configuration
if db_host is None or db_port is None or db_user is None or db_pass is None:
    log.error("OpenDB credentials not provided! Exiting...")
    exit(6)

if report_directory is None:
    log.error("No report directory provided! Exiting...")
    exit(7)

# fire up SSH tunnel
using_ssh_tunnel = ssh_host is not None and ssh_user is not None and ssh_pass is not None
tunnel = None
if using_ssh_tunnel:
    tunnel = ssh.start_tunnel(ssh_host=ssh_host, ssh_port=ssh_port, local_port=local_port,
                              ssh_user=ssh_user, ssh_pass=ssh_pass,
                              remote_host=db_host, remote_port=db_port)
    while not ssh.tunnel_active():
        time.sleep(0.5)

# fire up Oracle
dsn = cx_Oracle.makedsn('localhost', local_port, 'ORACLE') if using_ssh_tunnel \
    else cx_Oracle.makedsn(db_host, db_port, 'ORACLE')
db = cx_Oracle.connect(db_user, db_pass, dsn)
log.info("Database connected.")

# start preparing items which apply to most/all reports

# validate term argument
term = args['term']
p = re.compile('[1][0-9]{2}[1478]')
if term is not None and p.match(term) is None:
    log.error("Invalid term code provided! Exiting...")
    exit(5)
elif term is None:
    term = 'all'

# generate timestamp for reports
timestamp = time.strftime('%Y-%m-%d_%H%M%S')

# find which report is needed
report = args['report']
greedy = args['greedy']
if report == 'stale-courses':
    # run stale courses report
    report_path = report_directory + os.sep + 'stale-courses-' + term + '-' + timestamp + '.xls'
    stale_courses.run(connection=db, out_file_path=report_path)

elif report == 'force-completion':
    report_path = report_directory + os.sep + 'force-completion-' + term + '-' + timestamp + '.xls'
    force_completion.run(term=term, connection=db, out_file_path=report_path)

elif report == 'hardlinks':
    if term == 'all':
        log.error("Trying to run hardlinks report, but no term provided! Exiting...")
        exit(9)

    report_type = 'greedy-' if greedy else 'lazy-'
    report_path = report_directory + os.sep + 'hardlinks-' + report_type + term + '-' + timestamp + '.xls'
    hardlinks.run(term=term, connection=db, out_file_path=report_path, greedy=greedy)

elif report == 'mediafiles':
    media_config = config['MEDIA FILES']

    report_path = report_directory + os.sep + 'mediafiles-' + term + '-' + timestamp + '.xls'

    mediafiles.run(term=term, connection=db, out_file_path=report_path, threshold=media_config['mb_threshold'],
                   pattern=media_config['filename_pattern'])

elif report == 'orphaned-internal':
    report_path = report_directory + os.sep + 'orphaned-internal-' + timestamp + '.xls'

    orphanedinternal.run(db, report_path)

# close all connections
db.close()
log.info("Database connection disconnected.")
if using_ssh_tunnel:
    ssh.stop_tunnel()
    log.info("SSH Tunnel disconnected.")

log.info('Exiting...\n\n')
