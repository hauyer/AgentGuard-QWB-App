"""Dump live AgentGuard OpenAPI and validate pinned endpoints (B10)."""

import json
import sys
from pathlib import Path
from urllib.request import urlopen

base = "http://127.0.0.1:8000"
openapi = json.loads(urlopen(f"{base}/openapi.json", timeout=8).read().decode("utf-8"))
paths = sorted(openapi.get("paths", {}))

contract = json.load(open("contracts/agentguard-version.json", encoding="utf-8"))
pinned = set(contract["supported_endpoints"])
actual = {f"{method.upper()} {path}" for path, ops in openapi.get("paths", {}).items() for method in ops}

print(f"live paths: {len(paths)}")
missing = sorted(pinned - actual)
print(f"pinned endpoints missing from live OpenAPI: {missing if missing else 'NONE'}")

out = Path(__file__).resolve().parent.parent.parent / "integration-data" / "agentguard-openapi-7d42809.json"
out.write_text(json.dumps(openapi, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"openapi snapshot saved: {out}")
sys.exit(1 if missing else 0)
