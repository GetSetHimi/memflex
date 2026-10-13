# Copyright (c) 2026 Himanshu Sharma — Memflex, licensed under FSL-1.1-ALv2 (see LICENSE).
"""OTel tracing stub — no-op unless OTEL_EXPORTER_OTLP_ENDPOINT set."""
def setup_otel(app):
    try:
        import os
        if not os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT"):
            return
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        trace.set_tracer_provider(TracerProvider())
        trace.get_tracer_provider().add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    except Exception:
        pass
