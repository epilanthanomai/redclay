from redclay.logging import init_logging

init_logging()

import sys
from redclay.shell_command import run_from_argv

run_from_argv(sys.argv[1:])
