import io
import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from caching_service.api import create_app
from caching_service.cli.main import main, parse_args, run
from caching_service.cli.settings import InputError
from caching_service.config import Settings
from tests.conftest import CountingTransformer

SAMPLE_JSON = '{"list_1": ["a", "b"], "list_2": ["c", "d"]}'


class TestParseArgs:
    def test_defaults(self) -> None:
        settings = parse_args(["--json", SAMPLE_JSON])

        assert str(settings.host) == "http://localhost:8000/"
        assert settings.repeat == 1
        assert settings.output == "-"

    def test_short_flags(self, tmp_path: Path) -> None:
        settings = parse_args(
            ["-h", "http://example.com:9000", "-r", "3", "-i", "-", "-o", str(tmp_path / "o")]
        )

        assert str(settings.host) == "http://example.com:9000/"
        assert settings.repeat == 3
        assert settings.input == "-"
        assert settings.output == tmp_path / "o"

    @pytest.mark.parametrize(
        "argv",
        [
            [],
            ["-i", "-", "-j", SAMPLE_JSON],
            ["-j", SAMPLE_JSON, "-r", "0"],
            ["-j", SAMPLE_JSON, "-h", "not a url"],
        ],
        ids=["no-input", "two-inputs", "zero-repeat", "bad-host"],
    )
    def test_rejects_invalid_arguments(
        self, argv: list[str], capsys: pytest.CaptureFixture[str]
    ) -> None:
        assert main(argv) == 2
        assert capsys.readouterr().err.startswith("cache-cli: ")


class TestLoadRequest:
    def test_from_json_argument(self) -> None:
        request = parse_args(["-j", SAMPLE_JSON]).load_request()

        assert request.list_1 == ["a", "b"]
        assert request.list_2 == ["c", "d"]

    def test_from_file(self, tmp_path: Path) -> None:
        path = tmp_path / "input.json"
        path.write_text(SAMPLE_JSON)

        assert parse_args(["-i", str(path)]).load_request().list_2 == ["c", "d"]

    def test_from_stdin(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("sys.stdin", io.StringIO(SAMPLE_JSON))

        assert parse_args(["-i", "-"]).load_request().list_1 == ["a", "b"]

    @pytest.mark.parametrize(
        "raw",
        ["not json", '{"list_1": ["a"], "list_2": []}', '{"list_1": ["a"], "list_2": ["b", "c"]}'],
        ids=["malformed", "empty-list", "length-mismatch"],
    )
    def test_rejects_invalid_input(self, raw: str) -> None:
        with pytest.raises(InputError):
            parse_args(["-j", raw]).load_request()


@pytest.fixture
def client(tmp_path: Path, transformer: CountingTransformer) -> Iterator[TestClient]:
    settings = Settings(database_url=f"sqlite:///{tmp_path / 'cli.db'}")
    with TestClient(create_app(settings, transformer)) as client:
        yield client


def test_run_against_service(client: TestClient, transformer: CountingTransformer) -> None:
    request = parse_args(["-j", SAMPLE_JSON]).load_request()
    out = io.StringIO()

    run(request, repeat=3, client=client, out=out)

    results = [json.loads(line) for line in out.getvalue().splitlines()]
    assert [result["iteration"] for result in results] == [1, 2, 3]
    assert [result["created"] for result in results] == [True, False, False]
    assert len({result["id"] for result in results}) == 1
    assert all(result["output"] == "A, C, B, D" for result in results)
    assert sorted(transformer.calls) == ["a", "b", "c", "d"]


def test_main_reports_unreachable_host(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["-h", "http://127.0.0.1:1", "-j", SAMPLE_JSON]) == 1
    assert "request failed" in capsys.readouterr().err
