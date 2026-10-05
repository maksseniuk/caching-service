from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import Engine
from sqlmodel import Session

from caching_service.db import create_db_engine, init_db


class CountingTransformer:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def __call__(self, value: str, /) -> str:
        self.calls.append(value)
        return value.upper()


@pytest.fixture
def engine(tmp_path: Path) -> Iterator[Engine]:
    engine = create_db_engine(f"sqlite:///{tmp_path / 'test.db'}")
    init_db(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def session(engine: Engine) -> Iterator[Session]:
    with Session(engine) as session:
        yield session


@pytest.fixture
def transformer() -> CountingTransformer:
    return CountingTransformer()
