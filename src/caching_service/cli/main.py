import argparse
import json
import sys
import time
from collections.abc import Sequence
from pathlib import Path
from typing import Any, TextIO

import httpx2
from pydantic import ValidationError
from pydantic_settings import CliApp, CliSettingsSource

from caching_service.cli.settings import CliSettings, InputError, describe
from caching_service.schemas import PayloadCreate


def parse_args(argv: Sequence[str]) -> CliSettings:
    parser = argparse.ArgumentParser(prog="cache-cli", add_help=False)
    parser.add_argument("--help", action="help", help="Show this message and exit.")
    source: CliSettingsSource[CliSettings] = CliSettingsSource(CliSettings, root_parser=parser)
    return CliApp.run(CliSettings, cli_args=list(argv), cli_settings_source=source)


def run(request: PayloadCreate, repeat: int, client: httpx2.Client, out: TextIO) -> None:
    body = request.model_dump()
    for iteration in range(1, repeat + 1):
        started = time.perf_counter()
        created = client.post("/payload", json=body)
        created.raise_for_status()
        payload_id = created.json()["id"]
        read = client.get(f"/payload/{payload_id}")
        read.raise_for_status()
        result: dict[str, Any] = {
            "iteration": iteration,
            "id": payload_id,
            "created": created.status_code == httpx2.codes.CREATED,
            "output": read.json()["output"],
            "elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
        }
        out.write(json.dumps(result, ensure_ascii=False) + "\n")
        out.flush()


def main(argv: Sequence[str] | None = None) -> int:
    try:
        settings = parse_args(sys.argv[1:] if argv is None else argv)
        request = settings.load_request()
    except ValidationError as error:
        print(f"cache-cli: {describe(error)}", file=sys.stderr)
        return 2
    except (InputError, OSError) as error:
        print(f"cache-cli: {error}", file=sys.stderr)
        return 2

    try:
        with httpx2.Client(base_url=str(settings.host)) as client:
            if isinstance(settings.output, Path):
                with settings.output.open("w") as out:
                    run(request, settings.repeat, client, out)
            else:
                run(request, settings.repeat, client, sys.stdout)
    except httpx2.HTTPError as error:
        print(f"cache-cli: request failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
