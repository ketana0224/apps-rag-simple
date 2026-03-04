import logging
import os
from fastapi import FastAPI

_initialized = False


def setup_telemetry(app: FastAPI) -> None:
    global _initialized

    if _initialized:
        return

    connection_string = os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING", "").strip()
    if not connection_string:
        return

    try:
        from azure.monitor.opentelemetry.exporter import AzureMonitorTraceExporter
        from opentelemetry import trace
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        resource = Resource.create({"service.name": "apps-rag-simple"})
        tracer_provider = TracerProvider(resource=resource)
        exporter = AzureMonitorTraceExporter(connection_string=connection_string)
        tracer_provider.add_span_processor(BatchSpanProcessor(exporter))
        trace.set_tracer_provider(tracer_provider)
        FastAPIInstrumentor.instrument_app(
            app,
            tracer_provider=tracer_provider,
            exclude_spans=["receive", "send"],
        )
        _initialized = True
    except Exception:
        logging.getLogger(__name__).exception("telemetry initialization failed")
