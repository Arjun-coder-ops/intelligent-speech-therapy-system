"""
Structured logging and request correlation ID middleware for Flask.
Injects X-Correlation-ID into request context and response headers,
and measures HTTP request duration for observability metrics.
"""
import uuid
import time
import logging
from flask import Flask, request, g
from .metrics import metrics_collector


def setup_observability(app: Flask):
    """Register correlation ID and request timing middleware on Flask app."""

    @app.before_request
    def before_request_observability():
        # Read correlation ID from incoming headers or generate new UUID4
        correlation_id = (
            request.headers.get("X-Correlation-ID")
            or request.headers.get("X-Request-ID")
            or str(uuid.uuid4())
        )
        g.correlation_id = correlation_id
        g.start_time = time.time()

    @app.after_request
    def after_request_observability(response):
        # Calculate latency
        start_time = getattr(g, "start_time", None)
        duration = time.time() - start_time if start_time else 0.0

        correlation_id = getattr(g, "correlation_id", None)
        if correlation_id:
            response.headers["X-Correlation-ID"] = correlation_id

        # Record metrics (strip dynamic url parameters for endpoint labeling)
        endpoint = request.endpoint or request.path
        metrics_collector.record_request(
            method=request.method,
            endpoint=endpoint,
            status_code=response.status_code,
            duration_seconds=duration
        )

        # Structured application logging
        app.logger.info(
            "%s %s -> %s (%.2fms) [cid: %s]",
            request.method,
            request.path,
            response.status_code,
            duration * 1000,
            correlation_id
        )

        return response
