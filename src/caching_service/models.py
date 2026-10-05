import uuid
from datetime import UTC, datetime

from sqlmodel import Field, SQLModel


class TransformedString(SQLModel, table=True):
    __tablename__ = "transformed_strings"

    input: str = Field(primary_key=True)
    output: str


class Payload(SQLModel, table=True):
    __tablename__ = "payloads"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    input_hash: str = Field(unique=True, max_length=64)
    output: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
