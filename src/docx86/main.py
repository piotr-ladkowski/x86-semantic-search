"""FastAPI application factory.

Run:  uvicorn docx86.main:create_app --factory
The engine (content + vector index + embedder) is built once at startup and shared read-only by
all requests. If the index is stale the process refuses to start, so a bad rollout never becomes
Ready (set DOCX86_REBUILD_STALE_INDEX=1 in development to rebuild instead).
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.trace import NoOpTracer, Tracer
from starlette.exceptions import HTTPException as StarletteHTTPException

from . import __version__, api, telemetry, web
from .config import Settings, get_settings
from .content import load_content
from .embedding import get_embedder
from .index import IndexStaleError, build_index, ensure_fresh, load_index, save_index
from .search import SearchEngine

log = logging.getLogger("docx86")
PACKAGE_DIR = Path(__file__).parent


def build_engine(settings: Settings, tracer: Tracer | None = None) -> SearchEngine:
    tracer = tracer or NoOpTracer()
    with tracer.start_as_current_span("engine.build") as span:
        with tracer.start_as_current_span("content.load"):
            content = load_content(settings.content_dir)
        with tracer.start_as_current_span("embedder.init"):  # loads the ONNX model: the slow part
            embedder = get_embedder(settings)
        rebuilt = False
        with tracer.start_as_current_span("index.load"):
            try:
                index = load_index(settings.index_dir)
                ensure_fresh(index, content, embedder)
            except IndexStaleError as err:
                if not settings.rebuild_stale_index:
                    raise
                log.warning("Rebuilding stale index: %s", err)
                index = build_index(content, embedder)
                save_index(index, settings.index_dir)
                rebuilt = True
        span.set_attribute("docx86.instructions", len(content.instructions))
        span.set_attribute("docx86.articles", len(content.articles))
        span.set_attribute("docx86.index_units", len(index.units))
        span.set_attribute("docx86.embedder", embedder.id)
        span.set_attribute("docx86.index_rebuilt", rebuilt)
    log.info(
        "Loaded %d instructions, %d articles, %d index units (%s)",
        len(content.instructions),
        len(content.articles),
        len(index.units),
        embedder.id,
    )
    return SearchEngine(
        content, index, embedder, tracer=tracer, record_query=settings.trace_user_data
    )


def create_app(
    settings: Settings | None = None,
    engine: SearchEngine | None = None,
    tracer_provider: TracerProvider | None = None,
) -> FastAPI:
    """`tracer_provider` is for tests; normally tracing is configured from OTEL_* env vars."""
    settings = settings or get_settings()
    logging.basicConfig(
        level=settings.log_level, format="%(asctime)s %(levelname)s %(name)s %(message)s"
    )
    owns_provider = tracer_provider is None
    provider = tracer_provider if tracer_provider is not None else telemetry.build_provider()
    if provider is not None and not settings.trace_user_data:
        provider.add_span_processor(telemetry.ScrubUserData())
    tracer = provider.get_tracer("docx86", __version__) if provider else NoOpTracer()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        try:
            app.state.engine = engine or build_engine(settings, tracer)
            yield
        finally:
            # Also runs when startup fails (e.g. stale index), so that error trace is exported.
            if provider is not None and owns_provider:
                provider.shutdown()  # flushes buffered spans

    app = FastAPI(
        title="doc/x86",
        version=__version__,
        lifespan=lifespan,
        telemetry=telemetry.fastapi_config(provider),
    )
    app.mount("/static", StaticFiles(directory=PACKAGE_DIR / "static"), name="static")
    app.include_router(web.router)
    app.include_router(api.router, prefix="/api")

    @app.get("/healthz", include_in_schema=False)
    def healthz() -> dict:
        """Liveness: the process is up and serving."""
        return {"status": "ok"}

    @app.get("/readyz", include_in_schema=False)
    def readyz(request: Request) -> dict:
        """Readiness: content and index are loaded (startup fails otherwise)."""
        eng: SearchEngine = request.app.state.engine
        return {
            "status": "ready",
            "instructions": len(eng.content.instructions),
            "articles": len(eng.content.articles),
        }

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request: Request, exc: StarletteHTTPException):
        if request.url.path.startswith("/api") or exc.status_code != 404:
            return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)
        return web.templates.TemplateResponse(request, "404.html", {}, status_code=404)

    return app
