import uuid

import pytest
from sqlalchemy import Engine
from sqlmodel import Session

from caching_service.models import Payload
from caching_service.service import PayloadService, fingerprint, interleave
from tests.conftest import CountingTransformer

SAMPLE_1 = ["first string", "second string", "third string"]
SAMPLE_2 = ["other string", "another string", "last string"]


class TestInterleave:
    def test_alternates_items(self) -> None:
        assert interleave(["a", "b"], ["1", "2"]) == ["a", "1", "b", "2"]

    def test_empty(self) -> None:
        assert interleave([], []) == []

    def test_rejects_different_lengths(self) -> None:
        with pytest.raises(ValueError):
            interleave(["a"], [])


class TestFingerprint:
    def test_is_stable(self) -> None:
        assert fingerprint(SAMPLE_1, SAMPLE_2) == fingerprint(list(SAMPLE_1), list(SAMPLE_2))

    def test_respects_item_boundaries(self) -> None:
        assert fingerprint(["ab"], ["c"]) != fingerprint(["a"], ["bc"])

    def test_respects_list_order(self) -> None:
        assert fingerprint(["a"], ["b"]) != fingerprint(["b"], ["a"])


class TestPayloadService:
    def test_generates_sample_output(
        self, session: Session, transformer: CountingTransformer
    ) -> None:
        payload, created = PayloadService(session, transformer).create(SAMPLE_1, SAMPLE_2)

        assert created
        assert payload.output == (
            "FIRST STRING, OTHER STRING, SECOND STRING, ANOTHER STRING, THIRD STRING, LAST STRING"
        )

    def test_transforms_duplicate_strings_once(
        self, session: Session, transformer: CountingTransformer
    ) -> None:
        payload, _ = PayloadService(session, transformer).create(["a", "a"], ["a", "b"])

        assert payload.output == "A, A, A, B"
        assert sorted(transformer.calls) == ["a", "b"]

    def test_identical_request_reuses_payload_without_transforming(
        self, session: Session, transformer: CountingTransformer
    ) -> None:
        service = PayloadService(session, transformer)
        first, _ = service.create(SAMPLE_1, SAMPLE_2)
        calls_after_first = len(transformer.calls)

        second, created = service.create(SAMPLE_1, SAMPLE_2)

        assert not created
        assert second.id == first.id
        assert len(transformer.calls) == calls_after_first

    def test_new_payload_only_transforms_unseen_strings(
        self, session: Session, transformer: CountingTransformer
    ) -> None:
        service = PayloadService(session, transformer)
        service.create(["a", "b"], ["c", "d"])
        transformer.calls.clear()

        payload, created = service.create(["d", "c"], ["b", "e"])

        assert created
        assert payload.output == "D, B, C, E"
        assert transformer.calls == ["e"]

    def test_cache_persists_across_sessions(
        self, engine: Engine, transformer: CountingTransformer
    ) -> None:
        with Session(engine) as session:
            first, _ = PayloadService(session, transformer).create(["a"], ["b"])
        transformer.calls.clear()

        with Session(engine) as session:
            service = PayloadService(session, transformer)
            assert service.get(first.id) is not None
            service.create(["b"], ["a"])

        assert transformer.calls == []

    def test_get_unknown_returns_none(
        self, session: Session, transformer: CountingTransformer
    ) -> None:
        assert PayloadService(session, transformer).get(uuid.uuid4()) is None

    def test_concurrent_duplicate_resolves_to_existing_payload(
        self, engine: Engine, transformer: CountingTransformer, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        with Session(engine) as other_session:
            winner, _ = PayloadService(other_session, transformer).create(["a"], ["b"])

        with Session(engine) as session:
            service = PayloadService(session, transformer)
            # Simulate losing the race: the lookup misses, then the insert
            # collides with the row the other request already committed.
            original_find = service._find_by_hash
            lookups: list[str] = []

            def find_missing_first(input_hash: str) -> Payload | None:
                lookups.append(input_hash)
                return None if len(lookups) == 1 else original_find(input_hash)

            monkeypatch.setattr(service, "_find_by_hash", find_missing_first)

            payload, created = service.create(["a"], ["b"])

        assert len(lookups) == 2, "the IntegrityError fallback lookup did not run"

        assert not created
        assert payload.id == winner.id
