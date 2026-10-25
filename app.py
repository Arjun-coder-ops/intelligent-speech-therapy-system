import os
from flask import Flask, jsonify
from flask_cors import CORS

from config import Config
from extensions import db, jwt, bcrypt, migrate

from modules.auth.routes import auth_bp
from modules.assessments.routes import assess_bp
from modules.sentences.routes import sentences_bp
from modules.practice.routes import routes_bp
from modules.history.routes import history_bp
from modules.observability import setup_observability, observability_bp


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Ensure upload directory exists
    upload_folder = app.config.get("UPLOAD_FOLDER", "uploads")
    os.makedirs(upload_folder, exist_ok=True)

    # Extensions
    db.init_app(app)
    jwt.init_app(app)
    bcrypt.init_app(app)
    migrate.init_app(app, db)

    # Observability (Correlation IDs, timing, and structured logging)
    setup_observability(app)

    # CORS configuration - support configured origins and common dev ports
    raw_origins = os.getenv("FRONTEND_ORIGINS") or os.getenv("FRONTEND_ORIGIN") or "http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173"
    frontend_origins = [o.strip() for o in raw_origins.split(",") if o.strip()]

    CORS(
        app,
        resources={
            r"/*": {"origins": frontend_origins},
            r"/auth/*": {"origins": frontend_origins},
            r"/assessment/*": {"origins": frontend_origins},
            r"/sentences/*": {"origins": frontend_origins},
            r"/practice/*": {"origins": frontend_origins},
            r"/history/*": {"origins": frontend_origins},
            r"/metrics": {"origins": frontend_origins},
            r"/health/*": {"origins": frontend_origins},
        },
        supports_credentials=True,
        expose_headers=["Content-Type", "Authorization", "X-Correlation-ID"],
        allow_headers=["Content-Type", "Authorization", "X-Correlation-ID", "X-Request-ID"],
        methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"]
    )

    # Blueprints
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(assess_bp, url_prefix="/assessment")
    app.register_blueprint(sentences_bp, url_prefix="/sentences")
    app.register_blueprint(routes_bp, url_prefix="/practice")
    app.register_blueprint(history_bp, url_prefix="/history")
    app.register_blueprint(observability_bp, url_prefix="")

    @app.route("/")
    def home():
        return jsonify({
            "status": "online",
            "message": "Intelligent Speech Therapy Platform API is running",
            "endpoints": {
                "auth": "/auth",
                "assessment": "/assessment",
                "practice": "/practice",
                "sentences": "/sentences",
                "history": "/history",
                "metrics": "/metrics",
                "detailed_health": "/health/detailed"
            }
        }), 200

    with app.app_context():
        try:
            db.create_all()
        except Exception as e:
            app.logger.warning("db.create_all() encountered exception: %s", e)

    return app



if __name__ == "__main__":
    app = create_app()

    app.run(debug=True)
