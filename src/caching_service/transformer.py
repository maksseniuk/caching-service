import time
from typing import Protocol


class Transformer(Protocol):
    def __call__(self, value: str, /) -> str: ...


class UppercaseTransformer:
    def __init__(self, delay_seconds: float = 0.0) -> None:
        self._delay_seconds = delay_seconds

    def __call__(self, value: str, /) -> str:
        if self._delay_seconds > 0:
            time.sleep(self._delay_seconds)
        return value.upper()
