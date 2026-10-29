"""Real HTTP Study → AgentGuard → WARDEN Worker → verified result smoke test.

Start the three services and the independent Worker first. This script never
loads a model, starts a substitute executor, or manufactures experiment results.
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import httpx


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:18082")
    parser.add_argument("--project-id", type=int, required=True)
    parser.add_argument("--study-json", type=Path, required=True)
    parser.add_argument("--key", required=True, help="Retain this key for safe retries")
    parser.add_argument("--run-key", help="Optional existing Run idempotency key for recovery")
    parser.add_argument("--arm", default="baseline")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout", type=float, default=300)
    args = parser.parse_args()
    payload = json.loads(args.study_json.read_text(encoding="utf-8"))
    base = f"/api/projects/{args.project_id}/studies"
    with httpx.Client(base_url=args.base_url, timeout=30, trust_env=False) as client:
        created = client.post(base, json=payload, headers={"Idempotency-Key": args.key})
        created.raise_for_status()
        study_id = created.json()["submission"]["study_id"]
        if not study_id:
            raise RuntimeError("Study submission requires explicit reconciliation")
        submitted = client.post(
            f"{base}/{study_id}/runs", json={"arm_id": args.arm},
            headers={"Idempotency-Key": args.run_key or args.key + ":run"},
        )
        submitted.raise_for_status()
        state = submitted.json()
        if not state.get("workflow_id"):
            raise RuntimeError(f"Run not submitted: {state}")
        deadline = time.monotonic() + args.timeout
        while time.monotonic() < deadline:
            response = client.get(f"{base}/{study_id}/runs/{state['workflow_id']}")
            response.raise_for_status()
            result = response.json()
            status = (result.get("run") or {}).get("status") or result.get("status")
            if status == "completed":
                if result.get("source_validation") != "hash_and_study_verified":
                    raise RuntimeError("Completed run has no verified artifact")
                args.output.parent.mkdir(parents=True, exist_ok=True)
                args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
                print(json.dumps({"study_id": study_id, "run_id": result["run"]["run_id"],
                                  "source_validation": result["source_validation"],
                                  "analysis_status": result["analysis_status"]}))
                return 0
            if status in {"blocked", "failed", "cancelled"}:
                raise RuntimeError(f"Experiment did not complete: {result}")
            time.sleep(1)
        raise TimeoutError("Run remains unfinished; query its stable workflow ID before retrying")


if __name__ == "__main__":
    raise SystemExit(main())
