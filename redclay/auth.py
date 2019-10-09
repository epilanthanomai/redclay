import re
from crypt import crypt
from getpass import getpass

from sqlalchemy import Column, Integer, String

from redclay.modelbase import Base
from redclay.shell_command import subcommand, argument


class Account(Base):
    __tablename__ = "accounts"

    USERNAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{2,31}$")

    id = Column(Integer, primary_key=True)
    username = Column(String, nullable=False, unique=True)
    passhash = Column(String, nullable=False)

    def __init__(self, **kwargs):
        password = kwargs.pop("password", None)
        if password:
            kwargs["passhash"] = crypt(password)
        super().__init__(**kwargs)

    def __repr__(self):
        return f"<Account id={self.id}, username={self.username}>"

    @classmethod
    def valid_username(cls, username):
        return bool(cls.USERNAME_RE.match(username))

    def authenticate(self, password):
        return crypt(password, self.passhash) == self.passhash


@subcommand(argument("username"))
def create_account(session, username):
    if not Account.valid_username(username):
        print("Invalid username: " + username)
        return

    password = getpass()
    account = Account(username=username, password=password)
    session.add(account)
