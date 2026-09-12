from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from conformly.audit import models as audit_models
from conformly.compliance import models as compliance_models
from conformly.config import get_settings
from conformly.db.base import Base
from conformly.frameworks import models as framework_models
from conformly.identity import models as identity_models
from conformly.notifications import models as notification_models
from conformly.storage import models as storage_models

_ = (
    audit_models,
    compliance_models,
    framework_models,
    identity_models,
    notification_models,
    storage_models,
)

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

config.set_main_option("sqlalchemy.url", get_settings().database_url)
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
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
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
