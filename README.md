# Caching Service

A FastAPI microservice that builds payloads from two lists of strings, caching
the result of every call to a (simulated) external transformer so it is called
as rarely as possible. Includes `cache-cli`, a command line client for
exercising the service.

## How it works

`POST /payload` takes two lists of equal length. Every string is passed through
the transformer (it upper-cases, standing in for an external service), and the
transformed strings of both lists are interleaved and joined with `", "`.

Transformer calls are kept to a minimum on three levels:

1. **Identical request** – the request is fingerprinted (SHA-256 of its
   canonical JSON). If that fingerprint was seen before, the stored payload's
   identifier is returned and the transformer is not called at all.
2. **Known strings** – each distinct string's transformed value is cached in the
   `transformed_strings` table; a new request only transforms strings that are
   not in the cache yet.
3. **Duplicates within a request** – each distinct string is transformed once,
   however often it appears in either list.

`GET /payload/{id}` returns the stored output and never touches the transformer.

### API

| Method | Path             | Result                                                                                   |
| ------ | ---------------- | ---------------------------------------------------------------------------------------- |
| POST   | `/payload`       | `201` + `{"id", "message"}` for a new payload, `200` for one that already existed; `Location` header points at it |
| GET    | `/payload/{id}`  | `200` + `{"output"}`, `404` if unknown, `422` if `id` is not a UUID                     |
| GET    | `/health`        | Liveness probe used by the Docker health check                                           |

Validation (`422`): both lists must be present, non-empty, of the same length,
contain only strings, and stay within 1000 items of at most 1000 characters
each. Interactive docs are served at `/docs`.

```bash
curl -s localhost:8000/payload -H 'content-type: application/json' -d '{
  "list_1": ["first string", "second string", "third string"],
  "list_2": ["other string", "another string", "last string"]
}'
# {"id":"8f0c…","message":"Payload created"}

curl -s localhost:8000/payload/8f0c…
# {"output":"FIRST STRING, OTHER STRING, SECOND STRING, ANOTHER STRING, THIRD STRING, LAST STRING"}
```

## Running

Requires [uv](https://docs.astral.sh/uv/).

```bash
uv sync
uv run uvicorn caching_service.main:app --reload
```

With Docker (the SQLite database lives in the `cache-data` volume):

```bash
docker compose up --build
```

Configuration is read from environment variables (or a `.env` file):

| Variable                                  | Default                 | Purpose                                         |
| ----------------------------------------- | ----------------------- | ----------------------------------------------- |
| `CACHE_SERVICE_DATABASE_URL`              | `sqlite:///./cache.db`  | SQLAlchemy URL; SQLite and PostgreSQL supported |
| `CACHE_SERVICE_TRANSFORMER_DELAY_SECONDS` | `0`                     | Simulated latency per transformer call          |

Compose sets the delay to 0.2 s so the effect of the cache is visible in the
CLI's timings.

## CLI

```
cache-cli [-h|--host URL] [-r|--repeat N] [-i|--input FILE|-] [-j|--json JSON] [-o|--output FILE|-] [--help]
```

Exactly one of `--input` and `--json` is required. Each iteration creates the
payload, reads it back, and writes one JSON line:

```bash
uv run cache-cli -r 3 -j '{"list_1": ["a", "b"], "list_2": ["c", "d"]}'
# {"iteration": 1, "id": "…", "created": true,  "output": "A, C, B, D", "elapsed_ms": 812.4}
# {"iteration": 2, "id": "…", "created": false, "output": "A, C, B, D", "elapsed_ms": 3.1}
# {"iteration": 3, "id": "…", "created": false, "output": "A, C, B, D", "elapsed_ms": 2.9}

echo '{"list_1": ["a"], "list_2": ["b"]}' | uv run cache-cli -i - -o results.jsonl
```

Exit codes: `0` success, `1` HTTP or connection failure, `2` invalid arguments
or input.

## Development

```bash
uv run pytest        # unit + integration tests
uv run ruff check .  # lint
uv run mypy src tests
```

- `tests/test_service.py` – unit tests of the payload logic, using a
  transformer that counts its calls to prove what is and is not cached.
- `tests/test_api.py` – integration tests through HTTP against a real SQLite
  database.
- `tests/test_cli.py` – argument parsing and input loading, plus an end-to-end
  run of the CLI against the in-process app.

## Decisions and shortcuts

- **`-h` means `--host`.** The spec assigns `-h` to both `--host` and `--help`;
  host wins, so help is `--help` only.
- **Payload output is stored**, not recomputed from the string cache on read.
  Reads stay a single primary-key lookup and never depend on the transformer.
- **Payload ids are random UUIDs**, kept separate from the request fingerprint
  so the hashing scheme can change without invalidating identifiers.
- **Concurrent identical requests** are resolved by the unique constraint on
  the fingerprint: the loser rolls back and returns the winner's id. Two
  concurrent requests sharing a *new string* may both transform it; the
  second insert is ignored. Preventing that would need a lock or a
  request-coalescing layer, which is not worth it for a deterministic
  transformer.
- **No migrations.** Tables are created on startup with `create_all`; a real
  deployment would use Alembic.
- **No cache eviction.** Cached strings and payloads are kept forever.
- **Output format is ambiguous** when the input strings themselves contain
  `", "`. That is inherent to the format in the spec, so it is left as is.
- **The transformer is synchronous**, as is the database access, so the
  endpoints are plain `def` and run in FastAPI's thread pool.
