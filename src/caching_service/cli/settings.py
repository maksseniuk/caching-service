import sys
from pathlib import Path
from typing import Literal, Self

from pydantic import AliasChoices, Field, HttpUrl, PositiveInt, ValidationError, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from caching_service.schemas import PayloadCreate

STDIO: Literal["-"] = "-"

type URL = HttpUrl
type N = PositiveInt
type FILE = Path | Literal["-"]
type JSON = str


class InputError(ValueError):
    pass


class CliSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="CACHE_CLI_",
        cli_prog_name="cache-cli",
        cli_kebab_case=True,
        cli_hide_none_type=True,
    )

    host: URL = Field(
        default=HttpUrl("http://localhost:8000"),
        validation_alias=AliasChoices("h", "host"),
        description="Base URL of the caching service.",
    )
    repeat: N = Field(
        default=1,
        validation_alias=AliasChoices("r", "repeat"),
        description="Number of create/read iterations.",
    )
    input: FILE | None = Field(
        default=None,
        validation_alias=AliasChoices("i", "input"),
        description='JSON file with "list_1" and "list_2" ("-" for stdin).',
    )
    json_input: JSON | None = Field(
        default=None,
        validation_alias=AliasChoices("j", "json"),
        description="The same JSON document, passed inline.",
    )
    output: FILE = Field(
        default=STDIO,
        validation_alias=AliasChoices("o", "output"),
        description='File for the results ("-" for stdout).',
    )

    @model_validator(mode="after")
    def check_single_source(self) -> Self:
        if (self.input is None) == (self.json_input is None):
            raise ValueError("exactly one of --input or --json is required")
        return self

    def load_request(self) -> PayloadCreate:
        if self.json_input is not None:
            raw = self.json_input
        elif self.input == STDIO:
            raw = sys.stdin.read()
        else:
            assert isinstance(self.input, Path)
            raw = self.input.read_text()
        try:
            return PayloadCreate.model_validate_json(raw)
        except ValidationError as error:
            raise InputError(f"invalid input: {describe(error)}") from error


def describe(error: ValidationError) -> str:
    problems = []
    for item in error.errors(include_url=False):
        location = ".".join(str(part) for part in item["loc"])
        problems.append(f"{location}: {item['msg']}" if location else item["msg"])
    return "; ".join(problems)
