import os

bind = f"0.0.0.0:{os.getenv('PORT', '8000')}"
workers = int(os.getenv("GUNICORN_WORKERS", "1"))
worker_class = "uvicorn.workers.UvicornWorker"
timeout = int(os.getenv("GUNICORN_TIMEOUT", "120"))
accesslog = "-"
errorlog = "-"
loglevel = os.getenv("LOG_LEVEL", "info").lower()


def post_fork(server, worker):
    connection_string = os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING", "").strip()
    if not connection_string:
        server.log.warning("APPLICATIONINSIGHTS_CONNECTION_STRING is not set")
        return

    try:
        from azure.monitor.opentelemetry import configure_azure_monitor
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

        configure_azure_monitor(connection_string=connection_string)
        HTTPXClientInstrumentor().instrument()
        server.log.info("Application Insights initialized (pid=%s)", worker.pid)
    except Exception as exc:
        server.log.error("Application Insights initialization failed: %s", exc)
