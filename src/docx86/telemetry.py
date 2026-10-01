"""OpenTelemetry tracing. Configured with the standard OTEL_* environment variables.

Tracing is OFF unless an exporter is configured, and then costs nothing (no-op tracer):
    OTEL_EXPORTER_OTLP_ENDPOINT=http://collector:4318    -> export over OTLP/HTTP (protobuf)
    OTEL_TRACES_EXPORTER=console                         -> print spans to stdout (development)
    OTEL_SDK_DISABLED=true                               -> force off
Also honoured by the SDK itself: OTEL_SERVICE_NAME, OTEL_RESOURCE_ATTRIBUTES,
OTEL_TRACES_SAMPLER / OTEL_TRACES_SAMPLER_ARG, OTEL_EXPORTER_OTLP_HEADERS / _TIMEOUT, OTEL_BSP_*.

Only OTLP/HTTP is supported (port 4318, not gRPC 4317) to keep the image free of grpcio.

HTTP spans come from FastAPI's built-in telemetry (fastapi >= 0.142), not from the contrib
instrumentation package. We pass it our own provider and turn off its environment auto-configuration
and its metrics/logs signals: tracing is all we export, and FastAPI's "logs" signal would record
validation errors together with the user's original input.

Privacy: by default nothing the user typed is recorded. The search text travels in `?q=`, which
FastAPI puts in the `url.query` span attribute, so `ScrubUserData` redacts it as each span starts.
Set DOCX86_TRACE_USER_DATA=true to keep it and to add `docx86.search.query` to the search span.
"""

from __future__ import annotations

import os
import re
from collections.abc import MutableMapping
from typing import Any

from opentelemetry.context import Context
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import SERVICE_NAME, SERVICE_VERSION, Resource
from opentelemetry.sdk.trace import Span, SpanProcessor, TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    ConsoleSpanExporter,
    SimpleSpanProcessor,
)

from . import __version__

DEFAULT_SERVICE_NAME = "docx86"

# Stable (url.query) and legacy (http.url, http.target) semantic-convention names, plus the
# client-address attributes: scrubbed if a FastAPI/OTel upgrade ever starts recording them.
_URL_ATTRIBUTES = ("url.query", "url.full", "http.url", "http.target")
_CLIENT_ATTRIBUTES = ("client.address", "client.port", "net.peer.ip", "net.peer.port")
_QUERY_PARAM = re.compile(r"(?:^|(?<=[?&]))q=[^&#]*")


def _exporters_from_env() -> list[str]:
    raw = os.environ.get("OTEL_TRACES_EXPORTER", "")
    names = [n.strip().lower() for n in raw.split(",") if n.strip()]
    if names:
        return [n for n in names if n != "none"]
    has_endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT") or os.environ.get(
        "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT"
    )
    return ["otlp"] if has_endpoint else []


def _processor(name: str) -> SpanProcessor:
    if name == "otlp":
        protocol = os.environ.get(
            "OTEL_EXPORTER_OTLP_TRACES_PROTOCOL", os.environ.get("OTEL_EXPORTER_OTLP_PROTOCOL", "")
        ).lower()
        if protocol not in ("", "http/protobuf"):
            raise ValueError(
                f"OTEL_EXPORTER_OTLP_PROTOCOL={protocol!r} is not supported; this build exports "
                "OTLP over http/protobuf only (collector port 4318)"
            )
        return BatchSpanProcessor(OTLPSpanExporter())
    if name == "console":
        return SimpleSpanProcessor(ConsoleSpanExporter())
    raise ValueError(f"unsupported OTEL_TRACES_EXPORTER {name!r} (supported: otlp, console, none)")


def build_provider() -> TracerProvider | None:
    """A configured TracerProvider, or None when tracing is off. Raises ValueError on bad config."""
    if os.environ.get("OTEL_SDK_DISABLED", "").strip().lower() == "true":
        return None
    processors = [_processor(n) for n in _exporters_from_env()]
    if not processors:
        return None
    # Resource.create() reads OTEL_SERVICE_NAME / OTEL_RESOURCE_ATTRIBUTES. Our values are only
    # defaults: passing them to create() would override what the operator configured.
    resource = Resource.create()
    defaults: dict[str, str] = {}
    if str(resource.attributes.get(SERVICE_NAME, "")).startswith("unknown_service"):
        defaults[SERVICE_NAME] = DEFAULT_SERVICE_NAME
    if SERVICE_VERSION not in resource.attributes:
        defaults[SERVICE_VERSION] = __version__
    # The sampler comes from OTEL_TRACES_SAMPLER / OTEL_TRACES_SAMPLER_ARG.
    provider = TracerProvider(resource=resource.merge(Resource(defaults)))
    for p in processors:
        provider.add_span_processor(p)
    return provider


def redact_query(value: str) -> str:
    """Replace the value of the `q` parameter; other parameters (limit, kind) stay visible."""
    return _QUERY_PARAM.sub("q=REDACTED", value)


class ScrubUserData(SpanProcessor):
    """Overwrite attributes carrying the user's search text (or address) when a span starts.

    Runs in on_start, while the span is still writable and before any exporter sees it.
    """

    def on_start(self, span: Span, parent_context: Context | None = None) -> None:
        attributes = span.attributes or {}
        for key in _URL_ATTRIBUTES:
            value = attributes.get(key)
            if isinstance(value, str) and "q=" in value:
                span.set_attribute(key, redact_query(value))
        for key in _CLIENT_ATTRIBUTES:
            if key in attributes:
                span.set_attribute(key, "REDACTED")


def _exclude(scope: MutableMapping[str, Any]) -> bool:
    """Skip FastAPI telemetry for probes (every few seconds) and static assets."""
    path = scope.get("path", "")
    return path in ("/healthz", "/readyz") or path.startswith("/static/")


def fastapi_config(provider: TracerProvider | None) -> dict[str, Any]:
    """The `telemetry=` argument for FastAPI(): tracing through `provider`, nothing else."""
    return {
        "tracer_provider": provider,
        "tracing": provider is not None,
        "metrics": False,
        "logs": False,
        "auto_configure": False,  # never add environment exporters of its own
        "exclude": _exclude,
    }
