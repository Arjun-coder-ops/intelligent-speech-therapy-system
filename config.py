# from dotenv import load_dotenv
# from flask import Flask
# from flask_cors import CORS
# import os
# from flask_sqlalchemy import SQLAlchemy
# from flask_bcrypt import Bcrypt
# from flask_jwt_extended import JWTManager


# load_dotenv()

# app = Flask(__name__)

# POSTGRESQL_URI = os.getenv("POSTGRESQL_URI")
# SECRET_KEY = os.getenv("SECRET_KEY")

# app.config['SQLALCHEMY_DATABASE_URI'] = POSTGRESQL_URI
# app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
# app.config["SECRET_KEY"] = os.getenv("SECRET_KEY")
# app.config["JWT_SECRET_KEY"] = os.getenv("JWT_SECRET_KEY")

# CORS(app)
# jwt = JWTManager()
# db = SQLAlchemy()
# bcrypt = Bcrypt(app)


import os
from dotenv import load_dotenv

load_dotenv()
# OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")


class Config:
    SQLALCHEMY_DATABASE_URI = os.getenv("POSTGRESQL_URI")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Connection pool settings to prevent SSL timeout during long operations
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': 10,              # Number of connections to maintain
        'pool_recycle': 3600,         # Recycle connections after 1 hour
        'pool_pre_ping': True,        # Verify connections before using them
        'max_overflow': 20,           # Allow up to 20 additional connections
        'pool_timeout': 30,           # Timeout for getting connection from pool
        'connect_args': {
            'connect_timeout': 10,    # Connection timeout
            'keepalives': 1,          # Enable TCP keepalives
            'keepalives_idle': 30,    # Seconds before sending keepalive
            'keepalives_interval': 10,  # Seconds between keepalives
            'keepalives_count': 5     # Number of keepalives before giving up
        }
    }

    SECRET_KEY = os.getenv("SECRET_KEY")
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
