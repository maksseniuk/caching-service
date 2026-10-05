"""The "transformer function", standing in for a call to an external service."""

import time
from typing import Protocol


class Transformer(Protocol):
    def __call__(self, value: str, /) -> str: ...


class UppercaseTransformer:
    """Upper-cases its input, optionally sleeping to mimic network latency."""

    def __init__(self, delay_seconds: float = 0.0) -> None:
        self._delay_seconds = delay_seconds

    def __call__(self, value: str, /) -> str:
        if self._delay_seconds > 0:
            time.sleep(self._delay_seconds)
        return value.upper()
