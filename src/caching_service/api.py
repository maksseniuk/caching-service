import uuid
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from sqlmodel import Session

from caching_service.config import Settings
from caching_service.db import create_db_engine, init_db
from caching_service.schemas import PayloadCreate, PayloadCreated, PayloadRead
from caching_service.service import PayloadService
from caching_service.transformer import Transformer, UppercaseTransformer


def get_session(request: Request) -> Iterator[Session]:
    with Session(request.app.state.engine) as session:
        yield session


def get_service(
    request: Request, session: Annotated[Session, Depends(get_session)]
) -> PayloadService:
    return PayloadService(session, request.app.state.transformer)


ServiceDep = Annotated[PayloadService, Depends(get_service)]


def create_app(settings: Settings | None = None, transformer: Transformer | None = None) -> FastAPI:
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.engine = create_db_engine(settings.database_url)
        app.state.transformer = transformer or UppercaseTransformer(
            settings.transformer_delay_seconds
        )
        init_db(app.state.engine)
        yield
        app.state.engine.dispose()

    app = FastAPI(title="Caching Service", lifespan=lifespan)

    @app.post(
        "/payload",
        response_model=PayloadCreated,
        status_code=status.HTTP_201_CREATED,
        responses={status.HTTP_200_OK: {"model": PayloadCreated, "description": "Payload reused"}},
    )
    def create_payload(
        body: PayloadCreate, service: ServiceDep, response: Response
    ) -> PayloadCreated:
        payload, created = service.create(body.list_1, body.list_2)
        response.headers["Location"] = app.url_path_for("read_payload", payload_id=str(payload.id))
        if not created:
            response.status_code = status.HTTP_200_OK
            return PayloadCreated(id=payload.id, message="Payload already exists")
        return PayloadCreated(id=payload.id, message="Payload created")

    @app.get("/payload/{payload_id}", response_model=PayloadRead)
    def read_payload(payload_id: uuid.UUID, service: ServiceDep) -> PayloadRead:
        payload = service.get(payload_id)
        if payload is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Payload not found")
        return PayloadRead(output=payload.output)

    @app.get("/health", include_in_schema=False)
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app
