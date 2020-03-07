import contextlib
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


def get_db_url():
    return os.environ["RC_DB"]


def get_engine(**engine_args):
    return create_engine(get_db_url(), **engine_args)


def get_session_maker():
    return sessionmaker(bind=get_engine(), expire_on_commit=False)


@contextlib.contextmanager
def managed_session(Session=None):
    if Session is None:
        Session = get_session_maker()
    session = Session()
    try:
        yield session
        session.commit()
    except:
        session.rollback()
        raise
    finally:
        session.close()
