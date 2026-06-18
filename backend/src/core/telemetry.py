"""OpenTelemetry setup for GrantLayer — spans, trace_id propagation, exporters."""

from __future__ import annotations

import os
from typing import Any, Optional

_OTEL_AVAILABLE = False
_tracer: Any = None

try:
    from opentelemetry import trace as _otel_trace  # noqa: F401
    _OTEL_AVAILABLE = True
except ImportError:
    pass


def _env_str(name: str, default: str = "") -> str:
    return os.environ.get(name, default)


def _env_bool(name: str, default: bool = False) -> bool:
    v = os.environ.get(name, "").strip().lower()
    return v in ("1", "true", "yes") if v else default


def setup_telemetry(service_name: str = "grantlayer") -> None:
    """Initialize OTEL tracer provider. Idempotent — safe to call multiple times."""
    global _tracer, _OTEL_AVAILABLE
    if not _OTEL_AVAILABLE:
        return

    try:
        from opentelemetry import trace as _trace
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        resource = Resource.create({
            "service.name": service_name,
            "service.version": os.environ.get("GRANTLAYER_VERSION", "0.0.0"),
        })
        provider = TracerProvider(resource=resource)

        otlp_endpoint = _env_str("OTEL_EXPORTER_OTLP_ENDPOINT")
        if otlp_endpoint:
            try:
                from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
                exporter = OTLPSpanExporter(endpoint=otlp_endpoint)
                provider.add_span_processor(BatchSpanProcessor(exporter))
            except Exception:
                pass

        jaeger_host = _env_str("OTEL_JAEGER_HOST")
        if jaeger_host:
            try:
                from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
                jaeger_port = int(_env_str("OTEL_JAEGER_GRPC_PORT", "4317"))
                exporter = OTLPSpanExporter(endpoint=f"{jaeger_host}:{jaeger_port}")
                provider.add_span_processor(BatchSpanProcessor(exporter))
            except Exception:
                pass

        _trace.set_tracer_provider(provider)
        _tracer = _trace.get_tracer(service_name)
    except Exception:
        pass


def get_tracer() -> Any:
    """Return the module-level tracer (or a no-op shim if OTEL is unavailable)."""
    if _OTEL_AVAILABLE and _tracer is not None:
        return _tracer
    return _NoOpTracer()


def get_current_trace_id() -> Optional[str]:
    """Return the current span's trace ID as a hex string, or None."""
    if not _OTEL_AVAILABLE:
        return None
    try:
        from opentelemetry import trace
        span = trace.get_current_span()
        ctx = span.get_span_context()
        if ctx and ctx.trace_id:
            return format(ctx.trace_id, "032x")
    except Exception:
        pass
    return None


def instrument_fastapi(app: Any) -> None:
    """Apply FastAPI OTEL instrumentation (must be called after create_app)."""
    if not _OTEL_AVAILABLE:
        return
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        FastAPIInstrumentor.instrument_app(app)
    except Exception:
        pass


def instrument_sqlalchemy(engine: Any) -> None:
    """Apply SQLAlchemy OTEL instrumentation to an engine."""
    if not _OTEL_AVAILABLE:
        return
    try:
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
        SQLAlchemyInstrumentor().instrument(engine=engine)
    except Exception:
        pass


class _NoOpTracer:
    """Fallback tracer when OTEL is not available."""

    def start_as_current_span(self, name: str, **kwargs: Any):
        from contextlib import contextmanager

        @contextmanager
        def _ctx():
            yield _NoOpSpan()

        return _ctx()

    def start_span(self, name: str, **kwargs: Any) -> "_NoOpSpan":
        return _NoOpSpan()


class _NoOpSpan:
    def __enter__(self) -> "_NoOpSpan":
        return self

    def __exit__(self, *_: Any) -> None:
        pass

    def set_attribute(self, key: str, value: Any) -> None:
        pass

    def record_exception(self, exc: BaseException) -> None:
        pass
