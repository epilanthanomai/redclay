import asyncio
import contextlib
import functools
import logging

from redclay.game import run_shell
from redclay.logging import logging_context
from redclay.shell_command import subcommand
from redclay.terminal import Terminal

logger = logging.getLogger(__name__)


class ConnectionServer:
    async def handle_connection(self, run_shell, reader, writer):
        async with Terminal(reader, writer) as term:
            with logging_context(term=id(term)):
                try:
                    fileno = writer.get_extra_info("socket").fileno()
                    peername = writer.get_extra_info("peername")
                    sockname = writer.get_extra_info("sockname")

                    logger.info(
                        "new connection",
                        extra={"peer": peername, "sock": sockname, "fd": fileno},
                    )
                    conn = Connection(term)
                    await run_shell(conn)
                    logger.debug("shell exited normally")
                except EOFError:
                    logger.info("connection closed by peer")
                except:
                    logger.exception("connection closing from unhandled exception")
                else:
                    logger.info("connection closing normally")


class Connection:
    def __init__(self, term):
        self.term = term
        self.context_stack = [{}]
        self.running = True

    # context management

    def context(self):
        return self.context_stack[-1]

    def __getitem__(self, key):
        return self.context().get(key, None)

    # connection actions

    async def send_message(self, message):
        return await self.term.write(message)

    async def sleep(self, seconds):
        return await self.term.sleep(seconds)

    async def input(self, prompt):
        return await self.term.input(prompt)

    async def input_secret(self, prompt):
        return await self.term.input_secret(prompt)

    def _set_context(self, **kwargs):
        self.context().update(**kwargs)

    async def set_context(self, **kwargs):
        self._set_context(**kwargs)

    async def push(self, **kwargs):
        new_frame = self.context().copy()
        self.context_stack.append(new_frame)
        self._set_context(**kwargs)

    async def pop(self, **kwargs):
        self.context_stack.pop()
        self._set_context(**kwargs)

    async def stop(self):
        self.running = False


@subcommand()
def run_server():
    asyncio.run(async_run_server())


async def async_run_server():
    conn_server = ConnectionServer()
    handle = functools.partial(conn_server.handle_connection, run_shell)
    io_server = await asyncio.start_server(handle, "0.0.0.0", 6666)
    async with io_server:
        await io_server.serve_forever()
