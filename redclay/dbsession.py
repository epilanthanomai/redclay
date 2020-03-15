import contextlib
import os

from sqlalchemy import create_engine


def get_db_url():
    return os.environ["RC_DB"]


def get_engine(**engine_args):
    return create_engine(get_db_url(), **engine_args)
