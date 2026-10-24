"""Offline demo fixture service (B7 data source).

Every fixture file is registered in demo/fixtures/index.json with a SHA-256
hash; the service verifies the hash on first load and refuses to serve a
tampered fixture. Responses carry full provenance (meta) so the UI can label
RECORDED/SYNTHETIC replay data and never mistake it for a live backend.
"""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class DemoFixtureError(RuntimeError):
    """A fixture could not be loaded or failed its integrity check."""


class DemoService:
    def __init__(self, fixtures_dir: Path) -> None:
        self._dir = fixtures_dir
        self._index: list[dict] = []
        self._cache: dict[str, dict] = {}
        self._load_index()

    def _load_index(self) -> None:
        index_path = self._dir / "index.json"
        if not index_path.is_file():
            raise DemoFixtureError(f"fixture index missing: {index_path}")
        index = json.loads(index_path.read_text(encoding="utf-8"))
        self._index = index.get("fixtures", [])

    def fixture(self, name: str) -> dict:
        if name in self._cache:
            return self._cache[name]
        entry = next((item for item in self._index if item["file"] == name), None)
        if entry is None:
            raise DemoFixtureError(f"fixture not registered in index: {name}")
        path = self._dir / name
        if not path.is_file():
            raise DemoFixtureError(f"fixture file missing: {path}")
        raw = path.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        if digest != entry["sha256"]:
            raise DemoFixtureError(
                f"fixture integrity check failed for {name}: sha256 mismatch "
                f"(expected {entry['sha256']}, got {digest})"
            )
        payload = json.loads(raw.decode("utf-8"))
        self._cache[name] = payload
        return payload

    def meta_for(self, name: str) -> dict:
        entry = next((item for item in self._index if item["file"] == name), {})
        return entry

    # ------------------------------------------------------------------ #
    # typed queries (shapes mirror AgentGuard public API responses)
    # ------------------------------------------------------------------ #
    def list_investigations(self, *, status: str | None = None, limit: int = 50, offset: int = 0) -> dict:
        items = list(self.fixture("investigations.json")["items"])
        if status:
            items = [item for item in items if item.get("status") == status]
        total = len(items)
        page = items[offset : offset + limit]
        return {
            "items": page,
            "count": len(page),
            "offset": offset,
            "limit": limit,
            "total": total,
            "next_offset": offset + len(page) if offset + len(page) < total else None,
        }

    def get_investigation(self, request_id: str) -> dict | None:
        details = self.fixture("investigations.json").get("details", {})
        item = details.get(request_id)
        return dict(item) if item else None

    def get_timeline(self, request_id: str) -> list[dict]:
        items = self.fixture("timeline.json")["items"]
        return [event for event in items if event.get("request_id") == request_id]

    def get_evidence(self, request_id: str) -> dict | None:
        items = self.fixture("evidence.json")["items"]
        return items.get(request_id)

    def get_defense(self, request_id: str) -> dict | None:
        items = self.fixture("defense.json")["items"]
        return items.get(request_id)

    def historical_outcomes(self) -> list[dict]:
        return self.fixture("defense.json").get("historical_outcomes", [])

    def get_report(self, run_id: str) -> dict | None:
        items = self.fixture("reports.json")["items"]
        return items.get(run_id)

    def list_experiences(self) -> dict:
        return self.fixture("experiences.json")

    def list_experiments(self) -> dict:
        return self.fixture("experiments.json")

    def list_scenarios(self) -> dict:
        return self.fixture("scenarios.json")

    def get_graph(self) -> dict | None:
        return self.fixture("graph.json")

    # ------------------------------------------------------------------ #
    # aggregates used by the dashboard in demo mode
    # ------------------------------------------------------------------ #
    def investigation_summary(self) -> dict:
        items = self.fixture("investigations.json")["items"]
        counts = {"total": len(items), "running": 0, "completed": 0, "blocked": 0, "failed": 0, "pending": 0}
        for item in items:
            status = item.get("status")
            if status in counts:
                counts[status] += 1
        recent = max(items, key=lambda item: item.get("created_at", ""), default=None)
        return {
            **counts,
            "recent_request_id": recent.get("request_id") if recent else None,
            "recent_status": recent.get("status") if recent else None,
            "sample_based": False,
            "available": True,
        }

    def evidence_summary(self) -> dict:
        by_level: dict[str, int] = {}
        by_verification: dict[str, int] = {}
        for payload in self.fixture("evidence.json")["items"].values():
            for item in payload.get("items", []):
                level = item.get("evidence_level") or "unknown"
                verification = item.get("verification_status") or "unknown"
                by_level[level] = by_level.get(level, 0) + 1
                by_verification[verification] = by_verification.get(verification, 0) + 1
        return {
            "by_level": by_level,
            "by_verification": by_verification,
            "recent_count": sum(by_level.values()),
            "sample_based": False,
            "available": True,
        }

    def policy_summary(self) -> dict:
        pending = 0
        approved = 0
        unsupported = 0
        for payload in self.fixture("defense.json")["items"].values():
            for candidate in payload.get("candidates", []):
                status = candidate.get("status")
                if status == "pending_approval":
                    pending += 1
                elif status == "approved":
                    approved += 1
                if not candidate.get("execution_supported"):
                    unsupported += 1
        historical = len(self.historical_outcomes())
        return {
            "pending_approval": pending,
            "approved": approved,
            "unsupported": unsupported,
            "verified_historical": historical,
            "sample_based": False,
            "available": True,
        }
