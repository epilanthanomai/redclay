import asyncio
import logging
import re
import textwrap

from redclay.logging import logging_context
from redclay.terminal import Terminal


logger = logging.getLogger(__name__)


class Shell:
    USERNAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{2,31}$")
    BANNER = textwrap.dedent(
        """\
        Welcome to redclay, a Georgia MUD.

        """
    )
    WELCOME = textwrap.dedent(
        """\
        Welcome, {user}.
        """
    )
    GOODBYE = textwrap.dedent(
        """\
        Goodbye!
        """
    )

    def __init__(self, term):
        self.term = term

    @classmethod
    async def run_client(cls, reader, writer):
        async with Terminal(reader, writer) as term:
            with logging_context(term=id(term)):
                try:
                    fileno = writer.get_extra_info("socket").fileno()
                    peername = writer.get_extra_info("peername")
                    sockname = writer.get_extra_info("sockname")
                    shell = cls(term)

                    logger.info(
                        "new connection",
                        extra={"peer": peername, "sock": sockname, "fd": fileno},
                    )

                    await shell.run()
                    logger.debug(
                        f"shell:{id(shell)} exited normally",
                        extra=dict(shell=id(shell)),
                    )
                except EOFError:
                    logger.info("connection closed by peer")
                except:
                    logger.exception("connection closing from unhandled exception")
                else:
                    logger.info("connection closing normally")

    async def run(self):
        await self.term.write(self.BANNER)
        user = await self.login()
        if user:
            logger.info("successful login", extra={"user": user})
            await self.run_echo(user)
            await self.term.write(self.GOODBYE)
        else:
            logger.debug("closing without login")

    async def login(self):
        for _ in range(3):
            user = await self.login_once()
            if user:
                return user
            else:
                await self.term.sleep(1)

    async def login_once(self):
        username = await self.input_username()
        if not username:
            await self.term.write("Invalid username.\n\n")
            return
        password = await self.input_password()
        if self.authenticate(username, password):
            await self.term.write(self.WELCOME.format(user=username))
            return username
        else:
            logger.info("failed login", extra={"user": username})
            await self.term.write("Login failed.\n\n")
            return

    async def input_username(self):
        raw_username = await self.term.input("Username: ")
        stripped = raw_username.strip()
        if self.USERNAME_RE.match(stripped):
            return stripped
        else:
            logger.debug("invalid username", extra={"user": stripped})

    async def input_password(self):
        raw_password = await self.term.input_secret("Password: ")
        return raw_password.rstrip("\n")

    def authenticate(self, username, password):
        return password and username[-1] == password[-1]

    async def run_echo(self, user):
        while True:
            line = await self.input_echo_line(user)
            if line == "quit":
                break
            if line:
                await self.term.write(line + "\n")

    async def input_echo_line(self, user):
        line = await self.term.input(f"{user}> ")
        return line.strip()


async def run_server():
    server = await asyncio.start_server(Shell.run_client, "0.0.0.0", 6666)
    async with server:
        await server.serve_forever()
