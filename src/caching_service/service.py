import hashlib
import json
import uuid
from collections.abc import Collection, Sequence
from itertools import chain

from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, col, select

from caching_service.models import Payload, TransformedString
from caching_service.transformer import Transformer

OUTPUT_SEPARATOR = ", "


def interleave(first: Sequence[str], second: Sequence[str]) -> list[str]:
    if len(first) != len(second):
        raise ValueError("sequences must have the same length")
    return list(chain.from_iterable(zip(first, second, strict=True)))


def fingerprint(list_1: Sequence[str], list_2: Sequence[str]) -> str:
    canonical = json.dumps([list_1, list_2], ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


class PayloadService:
    def __init__(self, session: Session, transformer: Transformer) -> None:
        self._session = session
        self._transformer = transformer

    def get(self, payload_id: uuid.UUID) -> Payload | None:
        return self._session.get(Payload, payload_id)

    def create(self, list_1: Sequence[str], list_2: Sequence[str]) -> tuple[Payload, bool]:
        input_hash = fingerprint(list_1, list_2)
        existing = self._find_by_hash(input_hash)
        if existing is not None:
            return existing, False

        transformed = self._transform(set(list_1) | set(list_2))
        output = OUTPUT_SEPARATOR.join(transformed[value] for value in interleave(list_1, list_2))

        payload = Payload(input_hash=input_hash, output=output)
        self._session.add(payload)
        try:
            self._session.commit()
        except IntegrityError:
            self._session.rollback()
            winner = self._find_by_hash(input_hash)
            if winner is None:
                raise
            return winner, False
        self._session.refresh(payload)
        return payload, True

    def _find_by_hash(self, input_hash: str) -> Payload | None:
        statement = select(Payload).where(Payload.input_hash == input_hash)
        return self._session.exec(statement).first()

    def _transform(self, values: Collection[str]) -> dict[str, str]:
        statement = select(TransformedString).where(col(TransformedString.input).in_(values))
        results = {row.input: row.output for row in self._session.exec(statement)}

        missing = [value for value in values if value not in results]
        if not missing:
            return results

        fresh = {value: self._transformer(value) for value in missing}
        self._store(fresh)
        results.update(fresh)
        return results

    def _store(self, transformed: dict[str, str]) -> None:
        rows = [{"input": key, "output": value} for key, value in transformed.items()]
        dialect = self._session.get_bind().dialect.name
        statement: sqlite.Insert | postgresql.Insert
        if dialect == "sqlite":
            statement = sqlite.insert(TransformedString).values(rows).on_conflict_do_nothing()
        elif dialect == "postgresql":
            statement = postgresql.insert(TransformedString).values(rows).on_conflict_do_nothing()
        else:
            raise NotImplementedError(f"unsupported database dialect: {dialect}")
        self._session.execute(statement)
        self._session.commit()
