"""
In-memory Prometheus-compatible metrics collector.
Tracks HTTP requests, latencies, AI inference durations, LLM API calls, and fallbacks.
Thread-safe and lightweight with zero external runtime dependencies.
"""
import time
import threading
from collections import defaultdict
from typing import Dict, Any, List


class MetricsCollector:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(MetricsCollector, cls).__new__(cls)
                    cls._instance._init_metrics()
        return cls._instance

    def _init_metrics(self):
        self.lock = threading.Lock()
        self.start_time = time.time()

        # Counters: (key_tuple) -> count
        self.http_requests_total = defaultdict(int)
        self.ai_inference_total = defaultdict(int)
        self.llm_requests_total = defaultdict(int)
        self.llm_fallbacks_total = defaultdict(int)
        self.active_jobs = 0

        # Latency trackers: endpoint -> list of recent latencies (capped at 500)
        self.http_durations = defaultdict(list)
        self.inference_durations = []

    def record_request(self, method: str, endpoint: str, status_code: int, duration_seconds: float):
        endpoint_clean = endpoint or "/"
        with self.lock:
            self.http_requests_total[(method, endpoint_clean, str(status_code))] += 1
            dur_list = self.http_durations[endpoint_clean]
            dur_list.append(duration_seconds)
            if len(dur_list) > 500:
                dur_list.pop(0)

    def record_inference(self, duration_seconds: float, status: str = "success"):
        with self.lock:
            self.ai_inference_total[status] += 1
            self.inference_durations.append(duration_seconds)
            if len(self.inference_durations) > 500:
                self.inference_durations.pop(0)

    def record_llm_request(self, status: str = "success", duration_seconds: float = 0.0):
        with self.lock:
            self.llm_requests_total[status] += 1

    def record_llm_fallback(self, reason: str = "service_unavailable"):
        with self.lock:
            self.llm_fallbacks_total[reason] += 1

    def record_job_status(self, delta: int):
        with self.lock:
            self.active_jobs = max(0, self.active_jobs + delta)

    def get_summary(self) -> Dict[str, Any]:
        """Return a JSON-compatible dictionary summary of metrics."""
        with self.lock:
            uptime = round(time.time() - self.start_time, 2)
            total_requests = sum(self.http_requests_total.values())

            # Calculate p50 and p95 across all request durations
            all_durations = []
            for d_list in self.http_durations.values():
                all_durations.extend(d_list)

            all_durations.sort()
            p50 = all_durations[len(all_durations) // 2] if all_durations else 0.0
            p95_idx = int(len(all_durations) * 0.95)
            p95 = all_durations[p95_idx] if all_durations else 0.0

            inf_durs = sorted(self.inference_durations)
            inf_p50 = inf_durs[len(inf_durs) // 2] if inf_durs else 0.0
            inf_p95 = inf_durs[int(len(inf_durs) * 0.95)] if inf_durs else 0.0

            return {
                "uptime_seconds": uptime,
                "total_http_requests": total_requests,
                "latency_p50_seconds": round(p50, 4),
                "latency_p95_seconds": round(p95, 4),
                "ai_inference": {
                    "total": sum(self.ai_inference_total.values()),
                    "by_status": dict(self.ai_inference_total),
                    "p50_seconds": round(inf_p50, 4),
                    "p95_seconds": round(inf_p95, 4)
                },
                "llm": {
                    "requests_total": sum(self.llm_requests_total.values()),
                    "by_status": dict(self.llm_requests_total),
                    "fallbacks_total": sum(self.llm_fallbacks_total.values()),
                    "fallbacks_by_reason": dict(self.llm_fallbacks_total)
                },
                "active_background_jobs": self.active_jobs
            }

    def generate_prometheus_exposition(self) -> str:
        """Format metrics in official Prometheus text-based exposition format."""
        lines: List[str] = []
        with self.lock:
            lines.append("# HELP speechtherapy_uptime_seconds Application uptime in seconds")
            lines.append("# TYPE speechtherapy_uptime_seconds gauge")
            lines.append(f"speechtherapy_uptime_seconds {time.time() - self.start_time:.2f}")

            lines.append("# HELP speechtherapy_http_requests_total Total HTTP requests handled")
            lines.append("# TYPE speechtherapy_http_requests_total counter")
            for (method, endpoint, status), count in sorted(self.http_requests_total.items()):
                lines.append(f'speechtherapy_http_requests_total{{method="{method}",endpoint="{endpoint}",status="{status}"}} {count}')

            lines.append("# HELP speechtherapy_ai_inference_total Total AI speech assessment inferences")
            lines.append("# TYPE speechtherapy_ai_inference_total counter")
            for status, count in sorted(self.ai_inference_total.items()):
                lines.append(f'speechtherapy_ai_inference_total{{status="{status}"}} {count}')

            lines.append("# HELP speechtherapy_llm_requests_total Total LLM recommendation requests")
            lines.append("# TYPE speechtherapy_llm_requests_total counter")
            for status, count in sorted(self.llm_requests_total.items()):
                lines.append(f'speechtherapy_llm_requests_total{{status="{status}"}} {count}')

            lines.append("# HELP speechtherapy_llm_fallbacks_total Total LLM fallbacks triggered")
            lines.append("# TYPE speechtherapy_llm_fallbacks_total counter")
            for reason, count in sorted(self.llm_fallbacks_total.items()):
                lines.append(f'speechtherapy_llm_fallbacks_total{{reason="{reason}"}} {count}')

            lines.append("# HELP speechtherapy_active_background_jobs Currently running background assessment jobs")
            lines.append("# TYPE speechtherapy_active_background_jobs gauge")
            lines.append(f"speechtherapy_active_background_jobs {self.active_jobs}")

        return "\n".join(lines) + "\n"


metrics_collector = MetricsCollector()
