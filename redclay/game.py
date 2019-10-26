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


async def run_shell(term):
    await term.write(BANNER)
    username = await run_authentication(term)
    if username:
        logger.info("successful login", extra={"username": username})
        await term.write(WELCOME.format(user=username))
        await run_command_loop(term, username)
        await term.write(GOODBYE)
    else:
        logger.debug("closing without login")


#
# authentication
#


USERNAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{2,31}$")


async def run_authentication(term):
    for _ in range(3):
        username = await login_once(term)
        if username is not None:
            return username
        else:
            await term.sleep(1)


async def login_once(term):
    username = await input_username(term)
    if not username:
        await term.write("Invalid username.\n\n")
        return
    password = await input_password(term)
    if authenticate(username, password):
        return username
    else:
        logger.info("failed login", extra={"user": username})
        await term.write("Login failed.\n\n")


async def input_username(term):
    raw_username = await term.input("Username: ")
    stripped = raw_username.strip()
    if USERNAME_RE.match(stripped):
        return stripped
    else:
        logger.debug("invalid username", extra={"user": raw_username})


async def input_password(term):
    raw_password = await term.input_secret("Password: ")
    return raw_password.rstrip("\n")


def authenticate(username, password):
    return password and username[-1] == password[-1]


#
# command loop
#


async def run_command_loop(term, username):
    while True:
        line = await input_echo_line(term, username)
        if line == "quit":
            break
        if line:
            await term.write(line + "\n")


async def input_echo_line(term, username):
    line = await term.input(f"{username}> ")
    return line.strip()
