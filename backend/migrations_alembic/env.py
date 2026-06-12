import os
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# Add project root (parent of backend/) to sys.path so backend.src.* imports work.
_here = os.path.dirname(os.path.abspath(__file__))
_backend_dir = os.path.dirname(_here)          # backend/
_project_root = os.path.dirname(_backend_dir)  # project root
for _p in (_project_root, _backend_dir):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from backend.src.core.models import Base  # noqa: E402

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Override DB URL from environment variable if set.
_db_url = os.getenv("DATABASE_URL", os.getenv("GRANTLAYER_DATABASE_URL", ""))
if _db_url:
    config.set_main_option("sqlalchemy.url", _db_url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
