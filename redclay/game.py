import logging
import re
import textwrap

logger = logging.getLogger(__name__)

#
# shell
#

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


async def run_shell(conn):
    await conn.send_message(BANNER)
    username = await run_authentication(conn)
    if username:
        logger.info("successful login", extra={"username": username})
        await conn.send_message(WELCOME.format(user=username))
        await run_command_loop(conn, username)
        await conn.send_message(GOODBYE)
    else:
        logger.debug("closing without login")


#
# authentication
#


USERNAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{2,31}$")


async def run_authentication(conn):
    for _ in range(3):
        username = await login_once(conn)
        if username is not None:
            return username
        else:
            await conn.sleep(1)


async def login_once(conn):
    username = await input_username(conn)
    if not username:
        await conn.send_message("Invalid username.\n\n")
        return
    password = await input_password(conn)
    if authenticate(username, password):
        return username
    else:
        logger.info("failed login", extra={"user": username})
        await conn.send_message("Login failed.\n\n")


async def input_username(conn):
    raw_username = await conn.input("Username: ")
    stripped = raw_username.strip()
    if USERNAME_RE.match(stripped):
        return stripped
    else:
        logger.debug("invalid username", extra={"user": raw_username})


async def input_password(conn):
    raw_password = await conn.input_secret("Password: ")
    return raw_password.rstrip("\n")


def authenticate(username, password):
    return password and username[-1] == password[-1]


#
# command loop
#


async def run_command_loop(conn, username):
    while True:
        line = await input_echo_line(conn, username)
        if line == "quit":
            break
        if line:
            await conn.send_message(line + "\n")


async def input_echo_line(conn, username):
    line = await conn.input(f"{username}> ")
    return line.strip()
