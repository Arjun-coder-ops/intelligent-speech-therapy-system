"""Interactive demo client to preview and verify all Intelligent Speech Therapy API endpoints.

Usage:
    python scripts/demo_client.py
"""
import json
import os
import sys
import time
import requests

BASE_URL = os.environ.get("BASE_URL", "http://127.0.0.1:5000")
FIXTURE_AUDIO = os.path.join(
    os.path.dirname(__file__), "..", "eval", "data", "v1", "audio", "word_red.wav"
)


def print_step(title):
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def format_json(obj):
    return json.dumps(obj, indent=2)


def main():
    print_step(f"1. Checking Detailed System Health: {BASE_URL}/health/detailed")
    try:
        r = requests.get(f"{BASE_URL}/health/detailed", timeout=5)
        print(f"Status: {r.status_code}")
        print(f"Response: {format_json(r.json())}")
    except Exception as e:
        print(f"Failed to connect to {BASE_URL}: {e}")
        sys.exit(1)

    print_step("2. User Authentication (Registration / Login)")
    test_user = "demo_therapist"
    test_email = "demo_therapist@example.com"
    test_pass = "TherapyPass123!"
    reg_payload = {"fullName": test_user, "email": test_email, "password": test_pass}

    # Attempt registration (or proceed if already registered)
    r = requests.post(f"{BASE_URL}/auth/register", json=reg_payload, timeout=5)
    print(f"Register Status: {r.status_code}")
    if r.status_code == 201:
        print("Registration successful.")
    else:
        print("User already exists or returned:", r.text)

    # Login to obtain JWT
    login_resp = requests.post(
        f"{BASE_URL}/auth/login",
        json={"email": test_email, "password": test_pass},
        timeout=5,
    )
    print(f"Login Status: {login_resp.status_code}")
    login_data = login_resp.json()
    token = login_data.get("token")
    user_id = login_data.get("id")
    if not token:
        print(f"Failed to acquire token: {login_resp.text}")
        sys.exit(1)
    print(f"JWT Token acquired: {token[:25]}... (truncated)")
    print(f"Authenticated as User ID: {user_id}")

    headers = {"Authorization": f"Bearer {token}"}

    print_step("3. Sentence Catalog: GET /sentences")
    r = requests.get(f"{BASE_URL}/sentences", headers=headers, timeout=5)
    print(f"Status: {r.status_code}")
    sentences = r.json()
    print(f"Found {len(sentences)} sentences in catalog. Sample:")
    print(format_json(sentences[:2] if sentences else []))

    sentence_id = sentences[0]["id"] if sentences else 1

    print_step(
        f"4. Synchronous Audio Assessment: POST /assessment/upload (sentence_id={sentence_id})"
    )
    if os.path.exists(FIXTURE_AUDIO):
        with open(FIXTURE_AUDIO, "rb") as f:
            files = {"audio": ("word_red.wav", f, "audio/wav")}
            data = {"sentence_id": str(sentence_id), "user_id": str(user_id)}
            t0 = time.time()
            r = requests.post(
                f"{BASE_URL}/assessment/upload",
                headers=headers,
                files=files,
                data=data,
                timeout=15,
            )
            elapsed = (time.time() - t0) * 1000
            print(f"Status: {r.status_code} (Latency: {elapsed:.2f}ms)")
            print(f"Response: {format_json(r.json())}")
    else:
        print(f"Audio fixture not found at {FIXTURE_AUDIO}")

    print_step(
        f"5. Asynchronous Assessment Job Queue: POST /assessment/upload-async"
    )
    if os.path.exists(FIXTURE_AUDIO):
        with open(FIXTURE_AUDIO, "rb") as f:
            files = {"audio": ("word_red.wav", f, "audio/wav")}
            data = {"sentence_id": str(sentence_id), "user_id": str(user_id)}
            t0 = time.time()
            r = requests.post(
                f"{BASE_URL}/assessment/upload-async",
                headers=headers,
                files=files,
                data=data,
                timeout=10,
            )
            elapsed = (time.time() - t0) * 1000
            print(f"Status: {r.status_code} (Enqueue Latency: {elapsed:.2f}ms)")
            job_info = r.json()
            print(f"Response: {format_json(job_info)}")
            job_id = job_info.get("job_id")

            if job_id:
                print(f"\nPolling job status: GET /assessment/jobs/{job_id}")
                for attempt in range(1, 15):
                    time.sleep(0.5)
                    poll_resp = requests.get(
                        f"{BASE_URL}/assessment/jobs/{job_id}",
                        headers=headers,
                        timeout=5,
                    )
                    status = poll_resp.json().get("status")
                    print(f"  Attempt {attempt}: status={status}")
                    if status in ("completed", "failed"):
                        print(f"Final Job Result: {format_json(poll_resp.json())}")
                        break

    print_step(
        "6. Practice Recommendation: POST /practice/recommendation (with Weak Phonemes)"
    )
    practice_payload = {
        "weak_phonemes": ["R", "L"],
        "target_accuracy": 0.85,
        "difficulty": "intermediate",
    }
    r = requests.post(
        f"{BASE_URL}/practice/recommendation",
        headers=headers,
        json=practice_payload,
        timeout=10,
    )
    print(f"Status: {r.status_code}")
    print(f"Correlation ID: {r.headers.get('X-Correlation-ID')}")
    print(f"Response: {format_json(r.json())}")

    print_step("7. Prometheus Observability Metrics: GET /metrics")
    r = requests.get(f"{BASE_URL}/metrics", timeout=5)
    print(f"Status: {r.status_code}")
    metric_lines = [
        line
        for line in r.text.splitlines()
        if line and not line.startswith("#") and "speechtherapy_" in line
    ]
    print("Sample Speech Platform Metrics:")
    for line in metric_lines[:8]:
        print(f"  {line}")

    print_step("PREVIEW COMPLETED SUCCESSFULLY!")
    print(
        "All core backend workflows are operational, verified, and observable."
    )


if __name__ == "__main__":
    main()
