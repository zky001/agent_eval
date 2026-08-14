from collections.abc import AsyncGenerator

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base

from app.config import settings

# Convert sqlite:/// to sqlite+aiosqlite:///
database_url = settings.DATABASE_URL
if database_url.startswith("sqlite:///"):
    database_url = database_url.replace("sqlite:///", "sqlite+aiosqlite:///", 1)

engine = create_async_engine(
    database_url,
    echo=False,
    connect_args={"check_same_thread": False},
)


@event.listens_for(engine.sync_engine, "connect")
def set_sqlite_pragmas(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    # WAL lets readers proceed while a writer is active; NORMAL sync is the
    # recommended pairing and avoids an fsync per transaction.
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    # Wait instead of immediately failing with "database is locked" when
    # concurrent task writers collide.
    cursor.execute("PRAGMA busy_timeout=30000")
    # SQLite ships with FK enforcement off; the schema declares ON DELETE
    # CASCADE and relies on it.
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

Base = declarative_base()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# Hot-path indexes. create_all only creates indexes for brand-new tables, so
# they are also created explicitly to cover databases from older versions.
_INDEX_DDL = [
    "CREATE INDEX IF NOT EXISTS ix_tasks_run_id ON tasks (run_id)",
    "CREATE INDEX IF NOT EXISTS ix_tasks_status ON tasks (status)",
    "CREATE INDEX IF NOT EXISTS ix_dataset_items_dataset_id ON dataset_items (dataset_id)",
    "CREATE INDEX IF NOT EXISTS ix_evaluation_runs_dataset_id ON evaluation_runs (dataset_id)",
    "CREATE INDEX IF NOT EXISTS ix_evaluation_runs_model_config_id ON evaluation_runs (model_config_id)",
    "CREATE INDEX IF NOT EXISTS ix_evaluation_runs_status ON evaluation_runs (status)",
]

# Columns added after the initial release; create_all does not ALTER existing
# tables, so databases created by older versions get them here.
_COLUMN_MIGRATIONS = [
    ("evaluation_runs", "judge_model_config_id", "INTEGER REFERENCES model_configs(id)"),
    ("results", "input_tokens", "INTEGER"),
    ("results", "output_tokens", "INTEGER"),
    ("results", "trajectory", "TEXT"),
    ("model_configs", "input_price_per_million", "REAL"),
    ("model_configs", "output_price_per_million", "REAL"),
]


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        for table, column, ddl_type in _COLUMN_MIGRATIONS:
            existing = await conn.execute(text(f"PRAGMA table_info({table})"))
            if column not in {row[1] for row in existing}:
                await conn.execute(
                    text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl_type}")
                )
        for ddl in _INDEX_DDL:
            await conn.execute(text(ddl))
