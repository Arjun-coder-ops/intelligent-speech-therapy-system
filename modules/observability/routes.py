"""
Observability and Monitoring Routes.
Exposes /metrics (Prometheus text format) and /health/detailed (comprehensive JSON status).
"""
import os
import sys
from flask import Blueprint, jsonify, Response
from extensions import db
from .metrics import metrics_collector
from model_interface import get_model_status

observability_bp = Blueprint("observability", __name__)


@observability_bp.route("/metrics", methods=["GET"])
def prometheus_metrics():
    """Prometheus-compatible scraping endpoint."""
    exposition = metrics_collector.generate_prometheus_exposition()
    return Response(exposition, mimetype="text/plain; version=0.0.4; charset=utf-8")


@observability_bp.route("/health/detailed", methods=["GET"])
def detailed_health():
    """Detailed health check covering database, AI engine, and metrics summary."""
    # 1. Test database connectivity
    db_status = "connected"
    db_error = None
    try:
        db.session.execute(db.text("SELECT 1"))
    except Exception as e:
        db_status = "disconnected"
        db_error = str(e)

    # 2. Inspect AI Engine
    ai_status = get_model_status()

    # 3. Overall health status
    overall_status = "healthy"
    if db_status != "connected":
        overall_status = "degraded"

    return jsonify({
        "status": overall_status,
        "database": {
            "status": db_status,
            "error": db_error
        },
        "ai_engine": ai_status,
        "metrics_summary": metrics_collector.get_summary()
    }), 200
