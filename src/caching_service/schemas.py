import uuid
from typing import Annotated, Self

from pydantic import BaseModel, Field, StringConstraints, model_validator

MAX_ITEMS = 1000
MAX_ITEM_LENGTH = 1000

Item = Annotated[str, StringConstraints(max_length=MAX_ITEM_LENGTH)]
Items = Annotated[list[Item], Field(min_length=1, max_length=MAX_ITEMS)]


class PayloadCreate(BaseModel):
    list_1: Items
    list_2: Items

    @model_validator(mode="after")
    def check_same_length(self) -> Self:
        if len(self.list_1) != len(self.list_2):
            raise ValueError("list_1 and list_2 must have the same length")
        return self


class PayloadCreated(BaseModel):
    id: uuid.UUID
    message: str


class PayloadRead(BaseModel):
    output: str
