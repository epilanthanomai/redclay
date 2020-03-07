import asyncio
import contextlib
import functools
import logging

from redclay.dbsession import managed_session
from redclay.game import boot
from redclay.logging import logging_context
from redclay.shell_command import subcommand
from redclay.terminal import Terminal

logger = logging.getLogger(__name__)


class ConnectionServer:
    def __init__(self, Session):
        self.Session = Session

    async def handle_connection(self, boot, reader, writer):
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
                    conn = Connection(self.Session, term)
                    await self.run_conn(conn, boot)
                    logger.debug("shell exited normally")
                except EOFError:
                    logger.info("connection closed by peer")
                except:
                    logger.exception("connection closing from unhandled exception")
                else:
                    logger.info("connection closing normally")

    async def run_conn(self, conn, boot):
        await boot(conn)
        while conn.running:
            await self.run_prompt_once(conn)

    async def run_prompt_once(self, conn):
        prompt = conn["prompt"]
        raw_user_input = await self.get_user_input(conn)
        processed_input = raw_user_input.strip()
        with conn.get_managed_session():
            await prompt.handle_input(conn, processed_input)

    async def get_user_input(self, conn):
        prompt = conn["prompt"]
        prompt_text = prompt.prompt(conn) if callable(prompt.prompt) else prompt.prompt
        get_input = (
            conn.term.input_secret
            if getattr(prompt, "obscure_input", False)
            else conn.term.input
        )
        return await get_input(prompt_text)


class Connection:
    def __init__(self, Session, term):
        self.Session = Session
        self.session = None
        self.term = term
        self.context_stack = [{}]
        self.running = True

    # session management

    @contextlib.contextmanager
    def get_managed_session(self):
        with managed_session(self.Session) as session:
            self.session = session
            try:
                yield session
            finally:
                self.session = None

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
def run_server(Session):
    asyncio.run(async_run_server(Session))


async def async_run_server(Session):
    conn_server = ConnectionServer(Session)
    handle = functools.partial(conn_server.handle_connection, boot)
    io_server = await asyncio.start_server(handle, "0.0.0.0", 6666)
    async with io_server:
        await io_server.serve_forever()
