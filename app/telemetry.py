import logging
import os

_initialized = False


def setup_telemetry() -> None:
    global _initialized

    if _initialized:
        return

    connection_string = os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING", "").strip()
    if not connection_string:
        return

    try:
        from azure.monitor.opentelemetry import configure_azure_monitor

        configure_azure_monitor(connection_string=connection_string)
        _initialized = True
    except Exception:
        logging.getLogger(__name__).exception("telemetry initialization failed")
