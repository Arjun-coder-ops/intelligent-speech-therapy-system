# Intelligent Speech Therapy Platform - Backend

## 📋 Project Overview

The Intelligent Speech Therapy Platform Backend is a Flask-based RESTful API designed to support speech therapy assessment and practice. This system provides comprehensive functionality for user authentication, speech analysis, phoneme scoring, sentence-based practice, and progress tracking.

### Key Features
- **User Authentication**: Secure JWT-based authentication with bcrypt password hashing
- **Speech Assessment**: AI-powered speech assessment using OpenAI's Whisper model
- **Phoneme Analysis**: Detailed phoneme extraction and embedding comparison
- **Practice Sessions**: Interactive practice with immediate feedback
- **Progress Tracking**: Comprehensive history and assessment records
- **Database**: PostgreSQL with SQLAlchemy ORM
- **API Documentation**: RESTful API with CORS support for frontend integration

---

## 🏗️ Project Architecture

### Technology Stack
- **Framework**: Flask 3.1.2
- **Database**: PostgreSQL with SQLAlchemy ORM
- **Authentication**: Flask-JWT-Extended with Bcrypt
- **Speech Processing**: 
  - OpenAI Whisper (speech-to-text)
  - Librosa (audio processing)
  - Phoneme extraction with G2P-EN
- **Database Migrations**: Alembic & Flask-Migrate
- **CORS**: Flask-CORS for frontend communication

### Project Structure
```
Backend/
├── app.py                 # Main Flask application factory
├── config.py             # Configuration settings
├── extensions.py         # Database and authentication extensions
├── requirements.txt      # Python dependencies
├── migrations/           # Database migration files (Alembic)
├── models/              # Pre-trained embedding models
│   ├── embeddings/      # Phoneme embeddings (.npy files)
│   └── reference_audio/ # Reference audio samples
├── modules/             # Feature modules
│   ├── auth/           # User authentication & registration
│   ├── assessments/    # Speech assessment functionality
│   ├── practice/       # Practice session management
│   ├── sentences/      # Sentence data management
│   └── history/        # User history & progress tracking
├── scripts/            # Utility scripts for data processing
├── data/               # Training and reference data
└── temp/               # Temporary files
```

### Core Modules

| Module | Purpose |
|--------|---------|
| **auth** | User registration, login, JWT token management |
| **assessments** | Speech assessment API, scoring algorithms |
| **practice** | Practice session creation, phoneme feedback |
| **sentences** | Sentence data management and retrieval |
| **history** | User progress tracking and analytics |

---

## 🚀 Getting Started

### Prerequisites
- **Python**: 3.8 or higher
- **PostgreSQL**: 12 or higher
- **pip**: Python package manager

### Installation Steps

#### 1. Clone and Navigate to Backend Directory
```bash
cd Backend
```

#### 2. Create a Virtual Environment
```bash
# On Windows
python -m venv venv
venv\Scripts\activate

# On macOS/Linux
python3 -m venv venv
source venv/bin/activate
```

#### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

#### 4. Set Up Environment Variables
Create a `.env` file in the `Backend` directory with the following variables:

```env
# Database Configuration
POSTGRESQL_URI=postgresql://username:password@localhost:5432/db_name

# Secret Keys (generate strong random strings)
SECRET_KEY=your-secret-key-here
JWT_SECRET_KEY=your-jwt-secret-key-here

# OpenAI API Key 
OPENAI_API_KEY=your-openai-api-key-here
```

**Notes on Environment Variables:**
- Replace `username`, `password`, and `db_name` with your PostgreSQL credentials
- Generate strong secret keys using: `python -c "import secrets; print(secrets.token_hex(32))"`
- Ensure PostgreSQL is running and the database exists

#### 5. Initialize and Seed Database
```bash
# Initialize schema and seed default sentences (supports both PostgreSQL and SQLite fallback)
python scripts/seed_database.py
```

#### 6. Run Test Suite (Optional)
```bash
python tests/test_api.py
```

---

## 🔧 Running the Application

### Development Server
```bash
# Option 1: Using Flask directly
python app.py

# Option 2: Using Flask CLI
flask run
```

The API will be available at: **http://localhost:5000**

### Production Server
```bash
# Using Gunicorn (recommended for production on Linux)
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 "app:create_app()"
```

---

## 📡 API Endpoints

### Authentication (`/auth`)
- `POST /auth/register` - User registration (`fullName`, `email`, `password`, `confirmPassword`)
- `POST /auth/login` - User login (`email`, `password`) -> Returns JWT access token
- `GET /auth/me` - Get current user profile (requires `Bearer <token>`)

### Assessment (`/assessment`)
- `POST /assessment/upload` - Upload and analyze speech (multipart/form-data: `audio`, `sentence_id`, `user_id`)
- `GET /assessment/results/<id>` - Get specific assessment results
- `GET /assessment/history?user_id=<id>` - Get assessment history
- `GET /assessment/recommend?user_id=<id>` - Recommend a new sentence for the user

### Practice (`/practice`)
- `GET /practice/recommendation?weak_phonemes=<list>&weak_words=<list>` - Get 3 practice sentences (supports GET/POST)
- `POST /practice/submit` - Submit practice speech audio for evaluation

### Sentences (`/sentences`)
- `GET /sentences` - Get all available sentences (filter by `difficulty`, `source_type`)
- `GET /sentences/<id>` - Get specific sentence by ID
- `POST /sentences` - Create a new sentence (`text` or `sentence`, `difficulty`, `source_type`)
- `POST /sentences/add-bulk-sentences` - Bulk upload sentences array

### History (`/history`)
- `GET /history/prev_res?user_id=<id>` - Get user speech progress summary (also `/history/prev_results`)


---

## 🗄️ Database Setup

### PostgreSQL Installation
```bash
# Windows
# Download from: https://www.postgresql.org/download/windows/

# macOS
brew install postgresql@15

# Linux (Ubuntu)
sudo apt-get install postgresql postgresql-contrib
```

### Create Database
```sql
CREATE DATABASE speech_therapy_db;
```

### Run Migrations
```bash
flask db upgrade
```

To create a new migration after schema changes:
```bash
flask db migrate -m "Description of changes"
flask db upgrade
```

---

## 🔐 Security Features

- **JWT Authentication**: Secure token-based authentication
- **Password Hashing**: Bcrypt with salt for secure password storage
- **CORS Protection**: Restricted to frontend origin (http://localhost:5173)
- **SQL Injection Prevention**: SQLAlchemy ORM parameterized queries
- **Environment Variables**: Sensitive data stored in `.env` file

---

## 📦 Key Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| Flask | 3.1.2 | Web framework |
| Flask-SQLAlchemy | 3.1.1 | Database ORM |
| Flask-JWT-Extended | 4.7.1 | JWT authentication |
| Flask-Bcrypt | 1.0.1 | Password hashing |
| librosa | 0.11.0 | Audio processing |
| openai-whisper | 20250625 | Speech-to-text |
| g2p-en | 2.1.0 | Grapheme-to-phoneme |
| numpy | 2.3.5 | Numerical computing |
| Alembic | 1.17.2 | Database migrations |
| Flask-Migrate | 4.1.0 | Migration management |

See [requirements.txt](requirements.txt) for the complete list.

---

## 🐛 Troubleshooting

### Common Issues

**Issue: "No module named 'flask'"**
```bash
Solution: Activate virtual environment and reinstall dependencies
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt
```

**Issue: "PostgreSQL connection refused"**
```bash
Solution: Ensure PostgreSQL is running and credentials in .env are correct
# Check PostgreSQL status (Windows)
Get-Service postgresql-x64-*
# Or start it manually
pg_ctl -D "C:\Program Files\PostgreSQL\15\data" start
```

**Issue: "Relation does not exist" (after migrations)**
```bash
Solution: Run migrations
flask db upgrade
```

**Issue: JWT Token expired**
```bash
Solution: User should login again to get a new token
POST /auth/login with credentials
```

---

## 📝 Additional Scripts

Utility scripts are available in the `scripts/` directory:

- `generate_embeddings.py` - Generate phoneme embeddings
- `generate_phoneme_tts.py` - Generate text-to-speech for phonemes
- `verify_phoneme_audio.py` - Verify audio quality
- `score_phonemes.py` - Score phoneme pronunciation
- `forced_alignment.py` - Align audio with text

Run any script with:
```bash
python scripts/script_name.py
```

## 🤝 Development Workflow

1. Create a feature branch: `git checkout -b feature/your-feature`
2. Make your changes
3. Test thoroughly: `pytest` (if tests are configured)
4. Create database migration if needed: `flask db migrate`
5. Apply migrations: `flask db upgrade`
6. Commit and push changes
7. Create a pull request

---

## 📧 Environment Variables Reference

```
POSTGRESQL_URI          PostgreSQL connection string
SECRET_KEY             Flask session secret key
JWT_SECRET_KEY         JWT signing secret
OPENAI_API_KEY         Optional: OpenAI API key for Whisper
FLASK_ENV              development/production
```

---

## ✅ Verification Checklist

After setup, verify everything works:
- [ ] Virtual environment activated
- [ ] All dependencies installed (`pip list`)
- [ ] `.env` file configured with valid credentials
- [ ] PostgreSQL running and database created
- [ ] Migrations applied successfully
- [ ] Flask server starts without errors
- [ ] API responds to `GET http://localhost:5000/`
- [ ] Frontend can connect (CORS configured)

---

## 📚 Additional Resources

- [Flask Documentation](https://flask.palletsprojects.com/)
- [SQLAlchemy ORM Tutorial](https://docs.sqlalchemy.org/)
- [JWT Best Practices](https://tools.ietf.org/html/rfc8725)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)

---

## 📄 License

This project is part of the Infosys Internship Program (Nov Batch 8, 2025).

---

**Last Updated**: January 2026  
**Maintainer**: Backend Team