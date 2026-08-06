"""Smoke-test a running Customer Intelligence API.

Works against any instance: local uvicorn, a Docker container, or a deployed AWS URL.

    python -m scripts.smoke_test                              # http://127.0.0.1:8000
    python -m scripts.smoke_test --base-url http://127.0.0.1:8080
    python -m scripts.smoke_test --base-url https://<id>.ecs.ap-south-1.on.aws --require-real-models

Exit code 0 means every check passed, 1 means at least one failed, so this is safe to
use as a deployment gate in CI.
"""

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

EXAMPLES_DIR = Path(__file__).resolve().parent.parent / "examples"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Smoke-test a running Customer Intelligence API.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000", help="Base URL of the running API.")
    parser.add_argument("--timeout", type=float, default=30.0, help="Per-request timeout in seconds.")
    parser.add_argument(
        "--wait",
        type=float,
        default=0.0,
        help="Seconds to keep retrying /health before starting, for a container that is still booting.",
    )
    parser.add_argument(
        "--require-real-models",
        action="store_true",
        help="Fail if the API reports demo_mode: true. Use this against production.",
    )
    return parser.parse_args()


def request(method: str, url: str, payload: dict | None, timeout: float) -> tuple[int, object]:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {"Content-Type": "application/json"} if data else {}
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            body = response.read()
            try:
                return response.status, json.loads(body)
            except json.JSONDecodeError:
                return response.status, body[:200].decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        body = exc.read()
        try:
            return exc.code, json.loads(body)
        except json.JSONDecodeError:
            return exc.code, body[:200].decode("utf-8", "replace")


def wait_for_health(base_url: str, seconds: float, timeout: float) -> None:
    if seconds <= 0:
        return
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        try:
            status, _ = request("GET", f"{base_url}/health", None, timeout)
            if status == 200:
                return
        except Exception:
            pass
        time.sleep(1.0)
    print(f"  warning: /health did not return 200 within {seconds:.0f}s; continuing anyway")


def load_example(name: str) -> dict:
    return json.loads((EXAMPLES_DIR / name).read_text(encoding="utf-8"))


def main() -> int:
    args = parse_args()
    base_url = args.base_url.rstrip("/")

    print(f"Smoke-testing {base_url}")
    wait_for_health(base_url, args.wait, args.timeout)

    checks: list[tuple[str, str, str, dict | None, int]] = [
        ("health", "GET", "/health", None, 200),
        ("churn", "POST", "/predict/churn", load_example("churn_request.json"), 200),
        ("segment", "POST", "/segment/customer", load_example("segment_request.json"), 200),
        ("recommend", "POST", "/recommend", load_example("recommend_request.json"), 200),
        ("docs", "GET", "/docs", None, 200),
        (
            "rejects bad input",
            "POST",
            "/predict/churn",
            {"customer": {"customer_id": "x", "recency_days": -1, "frequency": 1, "monetary": 1,
                          "tenure_days": 1, "avg_order_value": 1, "total_items": 1, "unique_products": 1}},
            422,
        ),
    ]

    failures: list[str] = []
    health_body: object = None

    for label, method, path, payload, expected in checks:
        try:
            status, body = request(method, f"{base_url}{path}", payload, args.timeout)
        except Exception as exc:  # noqa: BLE001 - a smoke test should report, not raise
            failures.append(f"{label}: request failed ({exc})")
            print(f"  [FAIL] {label:<20} {method} {path} -> {exc}")
            continue

        if label == "health":
            health_body = body

        if status == expected:
            summary = ""
            if isinstance(body, dict):
                for key in ("churn_probability", "segment", "model_version"):
                    if key in body:
                        summary = f"  {key}={body[key]}"
                        break
                if "recommendations" in body:
                    summary = f"  {len(body['recommendations'])} recommendations"
            print(f"  [ok]   {label:<20} {method} {path} -> {status}{summary}")
        else:
            failures.append(f"{label}: expected {expected}, got {status}")
            print(f"  [FAIL] {label:<20} {method} {path} -> {status} (expected {expected})")

    if isinstance(health_body, dict):
        loaded = health_body.get("models_loaded", {})
        not_loaded = [name for name, ok in loaded.items() if not ok]
        if not_loaded:
            failures.append(f"models not loaded: {', '.join(not_loaded)}")
            print(f"  [FAIL] models not loaded: {', '.join(not_loaded)}")
        else:
            print(f"  [ok]   all models loaded    version={health_body.get('model_version')}")

        if health_body.get("demo_mode"):
            message = "API is running in demo mode (demo_mode: true)"
            if args.require_real_models:
                failures.append(message)
                print(f"  [FAIL] {message}")
            else:
                print(f"  [warn] {message} - pass --require-real-models to treat this as a failure")
        else:
            print("  [ok]   demo_mode: false     serving real trained models")

    print()
    if failures:
        print(f"FAILED - {len(failures)} problem(s):")
        for failure in failures:
            print(f"  - {failure}")
        return 1

    print("All smoke checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
