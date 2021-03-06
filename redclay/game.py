import logging
import re
import textwrap

logger = logging.getLogger(__name__)

BANNER = textwrap.dedent(
    """\
    Welcome to redclay, a Georgia MUD.

    """
)
MAX_TRIES = 3


async def boot(conn):
    await conn.send_message(BANNER)
    await conn.push(tag="auth", tries=0, prompt=UsernamePrompt()),


async def fail_actions(conn):
    tries = conn["tries"]
    new_tries = tries + 1

    if new_tries >= MAX_TRIES:
        logger.debug("closing without login")
        await conn.stop()
    else:
        await conn.set_context(tries=new_tries, prompt=UsernamePrompt())
        await conn.sleep(1)


class UsernamePrompt:
    USERNAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{2,31}$")
    prompt = "Username: "

    async def handle_input(self, conn, username):
        if not self.USERNAME_RE.match(username):
            await conn.send_message("Invalid username.\n\n")
            await fail_actions(conn)
        else:
            await conn.set_context(username=username, prompt=PasswordPrompt())


class PasswordPrompt:
    prompt = "Password: "
    obscure_input = True
    WELCOME = textwrap.dedent(
        """\
        Welcome, {user}.
        """
    )

    async def handle_input(self, conn, password):
        username = conn["username"]
        if password and username[-1] == password[-1]:
            logger.info("successful login", extra={"user": username})
            await conn.pop(username=username)
            await conn.send_message(self.WELCOME.format(user=username))
            await conn.push(tag="cmdloop", prompt=CommandPrompt())
        else:
            logger.info("failed login", extra={"user": username})
            await conn.send_message("Login failed.\n\n")
            await fail_actions(conn)


class CommandPrompt:
    GOODBYE = textwrap.dedent(
        """\
        Goodbye!
        """
    )

    def prompt(self, conn):
        return f"{conn['username']}> "

    async def handle_input(self, conn, line):
        if line == "quit":
            await conn.send_message(self.GOODBYE)
            await conn.stop()
        elif line:
            await conn.send_message(line + "\n")
