import asyncio
import logging
import re
import textwrap

from redclay.terminal import Terminal


logger = logging.getLogger(__name__)


class Shell:
    USERNAME_RE = re.compile(r'^[A-Za-z][A-Za-z0-9_-]{2,31}$')
    BANNER = textwrap.dedent('''\
        Welcome to redclay, a Georgia MUD.

        ''')
    WELCOME = textwrap.dedent('''\
        Welcome, {user}.
        ''')
    GOODBYE = textwrap.dedent('''\
        Goodbye!
        ''')

    def __init__(self, term):
        self.term = term

    @classmethod
    async def run_client(cls, reader, writer):
        async with Terminal(reader, writer) as term:
            try:
                fileno = writer.get_extra_info('socket').fileno()
                peername = writer.get_extra_info('peername')
                sockname = writer.get_extra_info('sockname')
                shell = cls(term)

                logger.info(
                    f'new connection '
                    f'fd:{fileno} '
                    f'peer:{peername} sock:{sockname} '
                    f'term:{id(term)} '
                    f'shell:{id(shell)}'
                )
                await shell.run()
                logger.debug(
                    f'shell:{id(shell)} exited normally',
                    extra=dict(
                       shell=id(shell)
                    ),
                )
            except EOFError:
                logger.info(f'connection closed by peer fd:{fileno}')
            except:
                logger.exception(
                    f'connection closing from unhandled exception '
                    f'fd:{fileno}'
                )
            else:
                logger.info(f'connection closing normally fd:{fileno}')

    async def run(self):
        await self.term.write(self.BANNER)
        user = await self.login()
        if user:
            logger.info(f'successful login user:{user} shell:{id(self)}')
            await self.run_echo(user)
            await self.term.write(self.GOODBYE)
        else:
            logger.debug(f'closing without login shell:{id(self)}')

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
            await self.term.write('Invalid username.\n\n')
            return
        password = await self.input_password()
        if self.authenticate(username, password):
            await self.term.write(
                self.WELCOME.format(user=username)
            )
            return username
        else:
            logger.info(f'failed login user:{username} shell:{id(self)}')
            await self.term.write('Login failed.\n\n')
            return

    async def input_username(self):
        raw_username = await self.term.input('Username: ')
        stripped = raw_username.strip()
        if self.USERNAME_RE.match(stripped):
            return stripped
        else:
            logger.debug(
                f'invalid username {raw_username!r} shell:{id(self)}'
            )

    async def input_password(self):
        raw_password = await self.term.input('Password: ')
        return raw_password.rstrip('\n')

    def authenticate(self, username, password):
        return password and username[-1] == password[-1]

    async def run_echo(self, user):
        while True:
            line = await self.input_echo_line(user)
            if line == 'quit':
                break
            if line:
                await self.term.write(line + '\n')

    async def input_echo_line(self, user):
            line = await self.term.input(f'{user}> ')
            return line.strip()


async def run_server():
    server = await asyncio.start_server(
        Shell.run_client, '127.0.0.1', 6666)
    async with server:
        await server.serve_forever()


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    asyncio.run(run_server())
