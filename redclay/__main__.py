import asyncio
import logging

from redclay.game import run_server

logging.basicConfig(level=logging.DEBUG)
asyncio.run(run_server())
