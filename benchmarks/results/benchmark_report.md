# Intelligent Speech Therapy Platform - Performance Benchmark Report
- **Timestamp:** `2026-10-25T10:44:57Z`
- **Platform:** `Windows-10-10.0.26300-SP0`
- **Python Version:** `3.10.8`

> [!NOTE]
> **Benchmark Scope & Limitations:** ML tensor operations were evaluated in lightweight fallback mode (without heavy CUDA Whisper/Wav2Vec2 weights).
> These measurements characterize the HTTP API gateway, database ORM transactions, LRU cache operations, and async thread pool dispatch latency.

## 1. HTTP Endpoint Latency & Throughput
| Endpoint | Iterations | p50 (ms) | p90 (ms) | p95 (ms) | p99 (ms) | Throughput (req/s) | Error Rate |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `GET /` | 100 | 0.48ms | 0.82ms | 0.96ms | 1.83ms | 1814.28 req/s | 0.0% |
| `GET /health/detailed` | 50 | 0.87ms | 1.67ms | 1.87ms | 2.1ms | 962.03 req/s | 0.0% |
| `GET /metrics` | 50 | 0.46ms | 0.82ms | 1.52ms | 1.65ms | 1800.59 req/s | 0.0% |
| `GET /sentences` | 100 | 1.52ms | 2.61ms | 2.73ms | 3.1ms | 572.86 req/s | 0.0% |
| `POST /practice/recommendation (Fallback)` | 50 | 3.17ms | 6.22ms | 6.69ms | 11.77ms | 271.08 req/s | 0.0% |

## 2. Audio LRU Cache Benchmark
- **Operations:** 1000 cached lookups
- **Lookup p50:** `0.8 µs`
- **Lookup p95:** `0.9 µs`
- **Cache Capacity:** `500` entries

## 3. Synchronous vs Asynchronous Audio Assessment Comparison
- **Synchronous Client Blocking Latency (p50):** `38.67 ms`
- **Asynchronous Enqueue Latency (Client HTTP 202 p50):** `21.95 ms`
- **Background Worker Execution Time (p50):** `140.54 ms`
- **Client Blocking Time Reduction:** Synchronous requests hold the client thread for the full execution cycle, whereas asynchronous submission returns an HTTP 202 in `21.95 ms`.
