"""
Observability Package for Intelligent Speech Therapy Platform.
Provides Prometheus-compatible metrics registry, structured logging with correlation IDs,
and health diagnostics.
"""

from .metrics import metrics_collector
from .logging_config import setup_observability
from .routes import observability_bp

__all__ = ["metrics_collector", "setup_observability", "observability_bp"]
