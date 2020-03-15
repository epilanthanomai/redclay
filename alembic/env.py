import os
import sys

env_path = os.path.abspath(__file__)
alembic_root = os.path.dirname(env_path)
project_root = os.path.dirname(alembic_root)
sys.path.append(project_root)

from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool

from redclay.dbsession import get_db_url, get_engine
from redclay.modelbase import load_models

config = context.config
fileConfig(config.config_file_name)


def run_migrations_offline():
    context.configure(
        url=get_db_url(),
        target_metadata=load_modls(),
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    engine = get_engine(poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=load_models())
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
