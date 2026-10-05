"""Database tables."""

import uuid
from datetime import UTC, datetime

from sqlmodel import Field, SQLModel


class TransformedString(SQLModel, table=True):
    """Cached result of a single transformer call, keyed by its input."""

    __tablename__ = "transformed_strings"

    input: str = Field(primary_key=True)
    output: str


class Payload(SQLModel, table=True):
    """A generated payload.

    The output is stored rather than rebuilt from the string cache so that
    reads never depend on the transformer, even if cache rows are evicted later.
    """

    __tablename__ = "payloads"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    # Fingerprint of the request; the unique constraint is what lets identical
    # requests (including concurrent ones) resolve to the same identifier.
    input_hash: str = Field(unique=True, max_length=64)
    output: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
