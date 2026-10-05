import uuid
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from caching_service.api import create_app
from caching_service.config import Settings
from tests.conftest import CountingTransformer

SAMPLE = {
    "list_1": ["first string", "second string", "third string"],
    "list_2": ["other string", "another string", "last string"],
}


@pytest.fixture
def client(tmp_path: Path, transformer: CountingTransformer) -> Iterator[TestClient]:
    settings = Settings(database_url=f"sqlite:///{tmp_path / 'api.db'}")
    with TestClient(create_app(settings, transformer)) as client:
        yield client


def test_create_then_read_sample(client: TestClient) -> None:
    created = client.post("/payload", json=SAMPLE)
    assert created.status_code == 201
    payload_id = created.json()["id"]
    assert created.headers["Location"] == f"/payload/{payload_id}"

    read = client.get(f"/payload/{payload_id}")

    assert read.status_code == 200
    assert read.json() == {
        "output": (
            "FIRST STRING, OTHER STRING, SECOND STRING, ANOTHER STRING, THIRD STRING, LAST STRING"
        )
    }


def test_repeated_post_reuses_identifier(
    client: TestClient, transformer: CountingTransformer
) -> None:
    first = client.post("/payload", json=SAMPLE)
    calls = len(transformer.calls)

    second = client.post("/payload", json=SAMPLE)

    assert second.status_code == 200
    assert second.json()["id"] == first.json()["id"]
    assert len(transformer.calls) == calls


def test_read_does_not_call_transformer(
    client: TestClient, transformer: CountingTransformer
) -> None:
    payload_id = client.post("/payload", json=SAMPLE).json()["id"]
    transformer.calls.clear()

    client.get(f"/payload/{payload_id}")

    assert transformer.calls == []


def test_read_unknown_payload(client: TestClient) -> None:
    assert client.get(f"/payload/{uuid.uuid4()}").status_code == 404


def test_read_malformed_identifier(client: TestClient) -> None:
    assert client.get("/payload/not-a-uuid").status_code == 422


@pytest.mark.parametrize(
    "body",
    [
        {"list_1": ["a"], "list_2": ["b", "c"]},
        {"list_1": [], "list_2": []},
        {"list_1": ["a"]},
        {"list_1": [1], "list_2": ["b"]},
        {"list_1": ["a" * 1001], "list_2": ["b"]},
    ],
    ids=["length-mismatch", "empty", "missing-list", "non-string", "item-too-long"],
)
def test_rejects_invalid_body(
    client: TestClient, transformer: CountingTransformer, body: dict[str, object]
) -> None:
    assert client.post("/payload", json=body).status_code == 422
    assert transformer.calls == []
