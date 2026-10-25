# Intelligent Speech Therapy Platform - Backend

Production-grade Flask RESTful API and applied AI inference pipeline for speech therapy assessment, phoneme articulation scoring, and personalized therapy recommendations.

---

## 📋 System Architecture

```mermaid
graph TD
    Client["Client / Frontend App"]
    GW["Flask API Gateway & Middleware\n(Correlation ID, Latency Tracking, CORS)"]
    Auth["JWT Authentication\n(bcrypt, claims)"]
    
    subgraph "Inference & Core Services"
        AssessSync["POST /assessment/upload\n(Synchronous Evaluation)"]
        AssessAsync["POST /assessment/upload-async\n(HTTP 202 Job Enqueue)"]
        WorkerPool["ThreadPoolExecutor Worker Pool\n(max_workers=2, Bounded Inference Semaphore)"]
        AudioModel["SpeechTherapyModel Singleton\n(Thread-Safe Audio LRU Cache, Wav2Vec2, Whisper)"]
        PracticeLLM["Practice Recommendation Engine\n(OpenRouter Llama 3.3, Exponential Backoff & Jitter)"]
        FallbackDB["Database-Backed Fallback Curated Corpus"]
    end
    
    subgraph "Storage & Observability"
        DB[("PostgreSQL / SQLite Storage\n(AudioRecord, AssessmentJob, Sentences, Users)")]
        Prometheus["GET /metrics\n(Prometheus Exposition Format)"]
        Health["GET /health/detailed\n(DB, Model Status, Cache, System Memory)"]
    end

    Client -->|HTTP Requests| GW
    GW --> Auth
    GW --> AssessSync
    GW --> AssessAsync
    GW --> PracticeLLM
    GW --> Prometheus
    GW --> Health
    
    AssessSync --> AudioModel
    AssessAsync -->|Enqueue Job| DB
    AssessAsync -->|Dispatch| WorkerPool
    WorkerPool --> AudioModel
    WorkerPool -->|Update Status & Results| DB
    
    PracticeLLM -->|External Call| OpenRouter["OpenRouter API"]
    PracticeLLM -.->|On Failure / Timeout| FallbackDB
    AudioModel --> DB
```

---

## 🚀 Key Engineering Upgrades

### 1. AI Evaluation and Regression Testing Pipeline
- **Word Error Rate (WER) & Character Error Rate (CER):** Rigorous dynamic-programming Levenshtein distance metrics separating substitutions, deletions, and insertions.
- **Versioned Evaluation Dataset:** Versioned test suite (`eval/data/v1/dataset.json`) with representative 16kHz PCM audio fixtures covering single-word articulation and continuous sentences.
- **LLM Schema & Resilience Testing:** Automated verification for JSON output structure, required fields, and boundary cases (timeout, rate limit 429, malformed output).
- **Regression Detection & Quality Gate:** Repeatable CLI runner (`python -m eval.run_eval`) comparing test runs against recorded baselines (`eval/baselines/baseline_v1.json`) with configurable regression tolerances and non-zero exit codes.
- **Automated Reporting:** Generates machine-readable JSON (`eval/reports/latest_eval_report.json`) and readable Markdown summaries (`latest_eval_report.md`).

### 2. Reliable, Observable AI Inference Pipeline
- **Thread-Safe Double-Checked Locking:** Thread-safe singleton model instantiation using reentrant locks (`threading.RLock`) preventing initialization races and deadlocks.
- **Bounded Concurrency Semaphore:** `threading.BoundedSemaphore(2)` prevents GPU/CPU memory exhaustion under high request volume.
- **Thread-Safe Audio LRU Cache:** In-memory `ThreadSafeAudioLRUCache` (capacity 100) caching feature extractions with sub-microsecond lookup times.
- **Resilient LLM Integration:** Bounded retries with exponential backoff and randomized jitter for transient HTTP 429/5xx errors, explicit 15-second request timeouts, and deterministic fallback tagging (`"fallback": true`, `"source": "database"`).
- **Structured Observability & Prometheus Metrics:**
  - Automatic `X-Correlation-ID` header injection and request duration logging.
  - `/metrics` endpoint exporting Prometheus text-format counters, gauges, and request latencies.
  - `/health/detailed` endpoint reporting comprehensive database, AI model, cache, and system health status.

### 3. Asynchronous Job Processing Pipeline
- **Non-blocking Enqueue:** `POST /assessment/upload-async` immediately persists an `AssessmentJob` in the database and returns HTTP 202 Accepted with job ID and status URL.
- **Background Execution:** Decoupled execution via `ThreadPoolExecutor(max_workers=2)` tracking explicit job states (`queued` -> `processing` -> `completed` / `failed`) and percentage progress.
- **Persistent State & User Isolation:** Complete job results stored in SQL database with JWT-based user authorization preventing cross-user data leakage.
- **Orphan Job Startup Recovery:** Automatically transitions any orphaned in-flight jobs left over from process crashes or server restarts into a terminal `failed` state.

---

## 📊 Performance Benchmarks

Measured on local test environment (Windows 10, Python 3.10.8):

> [!NOTE]
> **Benchmark Scope:** ML tensor operations were evaluated in lightweight fallback mode. Measurements characterize API routing, ORM database transactions, LRU cache data structures, and async thread pool dispatch latency.

| Endpoint / Operation | Sample Count | p50 Latency | p95 Latency | Throughput | Error Rate |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `GET /` | 100 reqs | **0.48 ms** | 0.96 ms | 1,814 req/s | 0.0% |
| `GET /health/detailed` | 50 reqs | **0.87 ms** | 1.87 ms | 962 req/s | 0.0% |
| `GET /metrics` | 50 reqs | **0.46 ms** | 1.52 ms | 1,800 req/s | 0.0% |
| `GET /sentences` | 100 reqs | **1.52 ms** | 2.73 ms | 572 req/s | 0.0% |
| `POST /practice/recommendation` (Fallback) | 50 reqs | **3.17 ms** | 6.69 ms | 271 req/s | 0.0% |
| `ThreadSafeAudioLRUCache` Lookup | 1,000 lookups | **0.80 µs** | 0.90 µs | >1,000,000 ops/s | 0.0% |
| Synchronous Assessment (Client Blocking) | 5 jobs | **38.67 ms** | 42.10 ms | Synchronous blocking | 0.0% |
| `POST /assessment/upload-async` (Enqueue) | 5 jobs | **21.95 ms** | 26.40 ms | Client unblocked (HTTP 202) | 0.0% |
| Background Job Worker Completion | 5 jobs | **140.54 ms** | 165.20 ms | Background worker pool | 0.0% |

---

## 🛠️ Installation & Local Setup

### 1. Prerequisites
- Python 3.8+ (tested on Python 3.10)
- PostgreSQL 12+ (or SQLite for testing/development)
- Virtual environment tool (`venv`)

### 2. Setup Environment
```bash
# Clone the repository
git clone https://github.com/Arjun-coder-ops/intelligent-speech-therapy-system.git
cd intelligent-speech-therapy-system

# Create and activate virtual environment
python -m venv venv
# On Windows:
venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Configure Environment Variables
Copy `.env.example` to `.env` and configure:
```env
# Database
POSTGRESQL_URI=postgresql://postgres:password@localhost:5432/speech_therapy
# If using SQLite for local development:
# SQLALCHEMY_DATABASE_URI=sqlite:///speech_therapy.db

# Security
SECRET_KEY=your-secure-secret-key
JWT_SECRET_KEY=your-jwt-secret-key

# AI Services
OPENROUTER_API_KEY=your-openrouter-key-here
FLASK_ENV=development
```

---

## 🧪 Running Tests & Quality Gates

### Run Complete Automated Test Suite (35 tests)
```bash
python -m pytest tests/ -v
```
Covers:
- `tests/test_api.py`: Core REST API integration tests (auth, sentences, assessments, history).
- `tests/test_ai_evaluation.py`: WER/CER edit-distance metrics, schema validation, dataset loader.
- `tests/test_inference_reliability.py`: ThreadSafe LRU cache, singleton locks, Prometheus metrics, `/health/detailed`, resilient LLM fallback.
- `tests/test_async_jobs.py`: Async job submission, HTTP 202 response, worker completion, user isolation.
- `tests/test_reliability_deep_audit.py`: Multi-threaded cache isolation, worker exception terminal states, orphan job startup recovery, LLM retry exhaustion.

### Run AI Evaluation & Regression Pipeline
```bash
# Run evaluation against baseline
python -m eval.run_eval

# Update recorded baseline
python -m eval.run_eval --update-baseline
```

### Run Performance Benchmarks
```bash
python benchmarks/run_benchmark.py
```

---

## 🌐 API Reference

### Health & Observability
| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/` | Service status and available API route directory |
| `GET` | `/health/detailed` | Comprehensive health check (DB connectivity, AI engine status, metrics summary) |
| `GET` | `/metrics` | Prometheus exposition format metrics (HTTP requests, AI inferences, LLM fallbacks) |

### Speech Assessment
| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/assessment/upload` | Synchronous audio upload and speech evaluation |
| `POST` | `/assessment/upload-async` | Asynchronous audio upload (returns HTTP 202 Accepted + `job_id`) |
| `GET` | `/assessment/jobs/<job_id>` | Poll job processing status (`queued`, `processing`, `completed`, `failed`) |
| `GET` | `/assessment/recommend?user_id=<id>` | Get recommended assessment sentence for a user |

### Practice & Therapy Recommendations
| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/practice/recommendation` | Generate LLM practice sentences tailored to weak phonemes (with DB fallback) |
| `POST` | `/practice/feedback` | Store user practice attempt feedback |

### Sentences & History
| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/sentences` | List all practice and assessment sentences |
| `GET` | `/sentences/<id>` | Retrieve specific sentence details |
| `POST` | `/sentences` | Create custom sentence |
| `GET` | `/history/<user_id>` | User assessment history and progress |

---

## 📄 License
This project is part of the Infosys Internship Program (Nov Batch 8, 2025).