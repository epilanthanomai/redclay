import logging
import textwrap

from redclay.auth import Account


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
    prompt = "Username: "

    async def handle_input(self, conn, username):
        if not Account.valid_username(username):
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
        account = self.authenticate(conn, username, password)
        if account:
            logger.info("successful login", extra={"user": username})
            await conn.pop(account=account)
            await conn.send_message(self.WELCOME.format(user=username))
            await conn.push(tag="cmdloop", prompt=CommandPrompt())
        else:
            logger.info("failed login", extra={"user": username})
            await conn.send_message("Login failed.\n\n")
            await fail_actions(conn)

    def authenticate(self, conn, username, password):
        if not password:
            return
        account = (
            conn.session.query(Account)
            .filter(Account.username == username)
            .one_or_none()
        )
        if account is not None and account.authenticate(password):
            return account


class CommandPrompt:
    GOODBYE = textwrap.dedent(
        """\
        Goodbye!
        """
    )

    def prompt(self, conn):
        return f"{conn['account'].username}> "

    async def handle_input(self, conn, line):
        if line == "quit":
            await conn.send_message(self.GOODBYE)
            await conn.stop()
        elif line:
            await conn.send_message(line + "\n")
