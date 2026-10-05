"""Database engine and schema setup."""

from sqlalchemy import Engine
from sqlmodel import SQLModel, create_engine

# Imported for its side effect of registering the tables on SQLModel.metadata.
from caching_service import models  # noqa: F401


def create_db_engine(database_url: str) -> Engine:
    connect_args: dict[str, object] = {}
    if database_url.startswith("sqlite"):
        # FastAPI runs sync endpoints in a thread pool, so a connection may be
        # used by a different thread than the one that opened it.
        connect_args["check_same_thread"] = False
    return create_engine(database_url, connect_args=connect_args)


def init_db(engine: Engine) -> None:
    # Shortcut: create_all instead of migrations (e.g. Alembic). Good enough
    # for a two-table schema that has not changed yet.
    SQLModel.metadata.create_all(engine)
