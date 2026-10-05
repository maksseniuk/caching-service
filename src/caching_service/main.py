"""ASGI entry point: ``uvicorn caching_service.main:app``."""

from caching_service.api import create_app

app = create_app()
