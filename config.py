import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent


class Config:
    # Database URL configuration with SQLite fallback for local development/testing
    _raw_uri = os.getenv("POSTGRESQL_URI") or os.getenv("DATABASE_URL")
    if _raw_uri:
        if _raw_uri.startswith("postgres://"):
            _raw_uri = _raw_uri.replace("postgres://", "postgresql://", 1)
        SQLALCHEMY_DATABASE_URI = _raw_uri
    else:
        # Fallback to local SQLite database if PostgreSQL URI is not configured
        default_db_path = BASE_DIR / "speech_therapy.db"
        SQLALCHEMY_DATABASE_URI = f"sqlite:///{default_db_path}"

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Connection pool settings - apply PostgreSQL-specific options only when connecting to PostgreSQL
    if SQLALCHEMY_DATABASE_URI.startswith("postgresql"):
        SQLALCHEMY_ENGINE_OPTIONS = {
            'pool_size': 10,
            'pool_recycle': 3600,
            'pool_pre_ping': True,
            'max_overflow': 20,
            'pool_timeout': 30,
            'connect_args': {
                'connect_timeout': 10,
                'keepalives': 1,
                'keepalives_idle': 30,
                'keepalives_interval': 10,
                'keepalives_count': 5
            }
        }
    else:
        SQLALCHEMY_ENGINE_OPTIONS = {}

    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-in-production")
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "dev-jwt-secret-key-change-in-production")
    OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
    UPLOAD_FOLDER = os.getenv("UPLOAD_FOLDER", str(BASE_DIR / "uploads"))
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50 MB max file size

