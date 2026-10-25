# Intelligent Speech Therapy Platform - Performance Benchmark Report
- **Timestamp:** `2026-10-25T05:38:14Z`
- **Platform:** `Windows-10-10.0.26300-SP0`
- **Python Version:** `3.10.8`

## 1. HTTP Endpoint Latency & Throughput
| Endpoint | Iterations | p50 (ms) | p90 (ms) | p95 (ms) | p99 (ms) | Throughput (req/s) | Error Rate |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `GET /` | 100 | 0.24ms | 0.48ms | 0.55ms | 0.69ms | 3431.85 req/s | 0.0% |
| `GET /health/detailed` | 50 | 0.49ms | 0.9ms | 0.97ms | 1.52ms | 1679.68 req/s | 0.0% |
| `GET /metrics` | 50 | 0.24ms | 0.39ms | 0.5ms | 0.81ms | 3816.33 req/s | 0.0% |
| `GET /sentences` | 100 | 0.77ms | 1.45ms | 1.61ms | 2.2ms | 1083.1 req/s | 0.0% |
| `POST /practice/recommendation (Fallback)` | 50 | 1.27ms | 2.08ms | 2.24ms | 11.44ms | 621.98 req/s | 0.0% |

## 2. Audio LRU Cache Benchmark
- **Operations:** 1000 cached lookups
- **Lookup p50:** `0.5 µs`
- **Lookup p95:** `0.7 µs`
- **Cache Capacity:** `500` entries

## 3. Asynchronous Job Processing Benchmark
- **Enqueue Latency (Client HTTP 202):** `16.69 ms`
- **Background Completion Time (p50):** `126.1 ms`
- **Client Non-Blocking Improvement:** Reduces synchronous request blocking to sub-30ms enqueue response.
