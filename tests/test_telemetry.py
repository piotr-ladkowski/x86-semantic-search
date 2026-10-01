import pytest
from fastapi.testclient import TestClient
from opentelemetry import metrics
from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import SpanKind

from docx86 import telemetry
from docx86.main import create_app

SECRET = "my very secret query"
TRACEPARENT = "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01"
OTEL_VARS = [
    "OTEL_SDK_DISABLED",
    "OTEL_TRACES_EXPORTER",
    "OTEL_METRICS_EXPORTER",
    "OTEL_LOGS_EXPORTER",
    "OTEL_SERVICE_NAME",
    "OTEL_RESOURCE_ATTRIBUTES",
    "OTEL_EXPORTER_OTLP_ENDPOINT",
    "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT",
    "OTEL_EXPORTER_OTLP_PROTOCOL",
    "OTEL_EXPORTER_OTLP_TRACES_PROTOCOL",
]


@pytest.fixture(autouse=True)
def clean_otel_env(monkeypatch):
    for name in OTEL_VARS:
        monkeypatch.delenv(name, raising=False)


def make_client(settings):
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    return TestClient(create_app(settings, tracer_provider=provider)), exporter


@pytest.fixture
def traced(settings):
    client, exporter = make_client(settings)
    with client:
        exporter.clear()  # drop the startup spans; see test_startup_spans
        yield client, exporter


def by_name(exporter, name):
    return [s for s in exporter.get_finished_spans() if s.name == name]


def all_attribute_text(exporter) -> str:
    return " ".join(
        f"{k}={v}" for s in exporter.get_finished_spans() for k, v in (s.attributes or {}).items()
    )


def test_startup_spans(settings):
    client, exporter = make_client(settings)
    with client:
        spans = {s.name: s for s in exporter.get_finished_spans()}
    assert {"engine.build", "content.load", "embedder.init", "index.load"} <= set(spans)
    root = spans["engine.build"]
    assert root.attributes["docx86.instructions"] == 3
    assert root.attributes["docx86.index_units"] > 3
    assert all(
        spans[n].parent.span_id == root.context.span_id
        for n in ("content.load", "embedder.init", "index.load")
    )


def test_search_request_produces_a_connected_trace(traced):
    client, exporter = traced
    assert client.get("/api/search", params={"q": "count set bits", "limit": 3}).status_code == 200

    (server,) = by_name(exporter, "GET /api/search")
    (endpoint,) = by_name(exporter, "fastapi.endpoint")
    (search,) = by_name(exporter, "search")
    (embed,) = by_name(exporter, "embed_query")
    assert server.kind == SpanKind.SERVER
    assert endpoint.parent.span_id == server.context.span_id
    assert search.parent.span_id == endpoint.context.span_id  # our spans nest under FastAPI's
    assert embed.parent.span_id == search.context.span_id
    assert len({s.context.trace_id for s in (server, endpoint, search, embed)}) == 1

    assert server.attributes["http.route"] == "/api/search"
    assert server.attributes["http.response.status_code"] == 200
    assert search.attributes["docx86.search.limit"] == 3
    assert search.attributes["docx86.search.results"] == 3
    assert search.attributes["docx86.search.top_slug"] == "popcnt"
    assert search.attributes["docx86.search.query_length"] == len("count set bits")
    assert embed.attributes["docx86.embedder"] == "hash:v1"


def test_span_names_use_the_route_template_not_the_url(traced):
    client, exporter = traced
    client.get("/instructions/lea")
    client.get("/instructions/popcnt")
    assert len(by_name(exporter, "GET /instructions/{name}")) == 2  # bounded cardinality


def test_incoming_traceparent_is_continued(traced):
    client, exporter = traced
    client.get("/api/search", params={"q": "x"}, headers={"traceparent": TRACEPARENT})
    (server,) = by_name(exporter, "GET /api/search")
    assert format(server.context.trace_id, "032x") == "0af7651916cd43dd8448eb211c80319c"
    assert format(server.parent.span_id, "016x") == "b7ad6b7169203331"


def test_probes_and_static_files_are_not_traced(traced):
    client, exporter = traced
    client.get("/healthz")
    client.get("/readyz")
    client.get("/static/does-not-matter.css")
    assert exporter.get_finished_spans() == ()


def test_html_search_embeds_the_query_once(traced):
    client, exporter = traced
    client.get("/search", params={"q": "a query that is searched twice"})
    assert len(by_name(exporter, "search")) == 2  # instructions, then articles
    assert len(by_name(exporter, "embed_query")) == 1  # second one hit the cache


def test_user_text_is_not_recorded_by_default(traced):
    client, exporter = traced
    client.get("/api/search", params={"q": SECRET, "limit": 2})
    client.get("/search", params={"q": SECRET})
    text = all_attribute_text(exporter)
    assert SECRET not in text and SECRET.replace(" ", "+") not in text
    (api,) = by_name(exporter, "GET /api/search")
    assert api.attributes["url.query"] == "q=REDACTED&limit=2"  # other params stay visible
    assert by_name(exporter, "GET /search")[0].attributes["url.query"] == "q=REDACTED"
    assert not any(
        "docx86.search.query" in (s.attributes or {}) for s in exporter.get_finished_spans()
    )


def test_opt_in_records_query_text(settings):
    client, exporter = make_client(settings.model_copy(update={"trace_user_data": True}))
    with client:
        exporter.clear()
        client.get("/api/search", params={"q": SECRET})
    (search,) = by_name(exporter, "search")
    assert search.attributes["docx86.search.query"] == SECRET
    (server,) = by_name(exporter, "GET /api/search")
    assert "REDACTED" not in server.attributes["url.query"]


def test_scrubber_also_covers_legacy_and_client_attributes():
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(telemetry.ScrubUserData())
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    attrs = {
        "http.url": "http://h/search?q=secret&limit=2",
        "url.full": "http://h/search?limit=2&q=secret",
        "client.address": "203.0.113.7",
        "net.peer.ip": "203.0.113.7",
        "url.path": "/search",
    }
    provider.get_tracer("t").start_span("s", attributes=attrs).end()
    (span,) = exporter.get_finished_spans()
    assert span.attributes["http.url"] == "http://h/search?q=REDACTED&limit=2"
    assert span.attributes["url.full"] == "http://h/search?limit=2&q=REDACTED"
    assert span.attributes["client.address"] == span.attributes["net.peer.ip"] == "REDACTED"
    assert span.attributes["url.path"] == "/search"


def test_only_traces_are_exported_even_if_the_environment_asks_for_more(monkeypatch, settings):
    """Left alone, FastAPI adds OTLP metric and log exporters from the shared endpoint variable."""

    def boom(*_a, **_k):
        raise AssertionError("a metrics/logs exporter was created")

    monkeypatch.setattr(OTLPMetricExporter, "__init__", boom)
    monkeypatch.setattr(OTLPLogExporter, "__init__", boom)
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://127.0.0.1:1")
    monkeypatch.setenv("OTEL_TRACES_EXPORTER", "console")  # traces to stdout, no network
    before = type(metrics.get_meter_provider())
    with TestClient(create_app(settings)) as client:
        assert client.get("/api/search", params={"q": "x"}).status_code == 200
    assert type(metrics.get_meter_provider()) is before


def test_failed_startup_is_exported_with_the_error(settings, tmp_path):
    strict = settings.model_copy(
        update={"rebuild_stale_index": False, "index_dir": tmp_path / "missing-index"}
    )
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    with (
        pytest.raises(Exception, match="no index"),
        TestClient(create_app(strict, tracer_provider=provider)),
    ):
        pass
    build = by_name(exporter, "engine.build")[0]
    assert build.status.status_code.name == "ERROR"
    assert any(e.name == "exception" for e in build.events)


def test_tracing_is_off_without_configuration():
    assert telemetry.build_provider() is None


def test_app_without_tracing_has_no_telemetry_overhead(client):
    assert client.get("/api/search", params={"q": "x"}).status_code == 200


def test_sdk_disabled_wins(monkeypatch):
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://collector:4318")
    monkeypatch.setenv("OTEL_SDK_DISABLED", "true")
    assert telemetry.build_provider() is None


def test_otlp_endpoint_enables_batch_export(monkeypatch):
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://collector:4318")
    provider = telemetry.build_provider()
    try:
        procs = provider._active_span_processor._span_processors
        assert len(procs) == 1 and isinstance(procs[0], BatchSpanProcessor)
        assert provider.resource.attributes["service.name"] == "docx86"
        assert provider.resource.attributes["service.version"]
    finally:
        provider.shutdown()


def test_explicit_none_exporter_disables(monkeypatch):
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://collector:4318")
    monkeypatch.setenv("OTEL_TRACES_EXPORTER", "none")
    assert telemetry.build_provider() is None


def test_default_service_name_applies_when_env_is_silent(monkeypatch):
    monkeypatch.setenv("OTEL_TRACES_EXPORTER", "console")
    monkeypatch.setenv("OTEL_RESOURCE_ATTRIBUTES", "k8s.pod.name=pod-1")
    provider = telemetry.build_provider()
    try:
        assert provider.resource.attributes["service.name"] == "docx86"
    finally:
        provider.shutdown()


def test_standard_resource_env_overrides_defaults(monkeypatch):
    monkeypatch.setenv("OTEL_TRACES_EXPORTER", "console")
    monkeypatch.setenv("OTEL_SERVICE_NAME", "custom-name")
    monkeypatch.setenv("OTEL_RESOURCE_ATTRIBUTES", "k8s.pod.name=pod-1,deployment.environment=prod")
    provider = telemetry.build_provider()
    try:
        attrs = provider.resource.attributes
        assert attrs["service.name"] == "custom-name"
        assert attrs["k8s.pod.name"] == "pod-1" and attrs["deployment.environment"] == "prod"
    finally:
        provider.shutdown()


@pytest.mark.parametrize(
    ("var", "value", "message"),
    [
        ("OTEL_TRACES_EXPORTER", "jaeger", "unsupported OTEL_TRACES_EXPORTER"),
        ("OTEL_EXPORTER_OTLP_PROTOCOL", "grpc", "http/protobuf only"),
    ],
)
def test_misconfiguration_fails_fast(monkeypatch, var, value, message):
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://collector:4317")
    monkeypatch.setenv(var, value)
    with pytest.raises(ValueError, match=message):
        telemetry.build_provider()


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("q=secret+words&limit=2", "q=REDACTED&limit=2"),  # FastAPI's url.query form
        ("limit=2&q=a%20b&kind=x", "limit=2&q=REDACTED&kind=x"),
        ("/api/search?q=secret+words&limit=2", "/api/search?q=REDACTED&limit=2"),
        ("http://h/search?limit=2&q=a%20b&kind=x", "http://h/search?limit=2&q=REDACTED&kind=x"),
        ("q=", "q=REDACTED"),
        ("/instructions/add", "/instructions/add"),
        ("faq=keep&q2=keep", "faq=keep&q2=keep"),  # only the exact parameter `q`
    ],
)
def test_redact_query(raw, expected):
    assert telemetry.redact_query(raw) == expected
