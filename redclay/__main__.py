from redclay.logging import init_logging

init_logging()

import asyncio
from redclay.game import run_server

asyncio.run(run_server())
