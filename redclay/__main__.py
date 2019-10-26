from redclay.logging import init_logging

init_logging()

import sys
from redclay.shell_command import run_from_argv

SUBCOMMANDS = ["redclay.server.run_server"]

run_from_argv(SUBCOMMANDS, sys.argv[1:])
