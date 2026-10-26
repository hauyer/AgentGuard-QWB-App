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
import re
from pathlib import Path

logger = logging.getLogger(__name__)
PINNED_FIXTURE_INDEX_SHA256 = "5ef5d0bacd3b574aa007c5391e5d9983092a4f292412f0c3cb2f304b098efdce"
_SHA256_RE = re.compile(r"^[a-f0-9]{64}$")


class DemoFixtureError(RuntimeError):
    """A fixture could not be loaded or failed its integrity check."""


class DemoService:
    def __init__(self, fixtures_dir: Path) -> None:
        self._dir = fixtures_dir
        self._index: list[dict] = []
        self._cache: dict[str, dict] = {}
        self._overlay: dict[str, dict] = {}
        self._load_index()

    # ------------------------------------------------------------------ #
    # demo-only submission overlay (never a real WARDEN run)
    # ------------------------------------------------------------------ #
    def record_demo_investigation(self, request_id: str, item: dict) -> dict:
        self._overlay[request_id] = item
        return item

    def _load_index(self) -> None:
        root = self._dir.resolve()
        index_path = (root / "index.json").resolve()
        try:
            index_path.relative_to(root)
        except ValueError as exc:
            raise DemoFixtureError("fixture index must stay inside the fixture directory") from exc
        if not index_path.is_file():
            raise DemoFixtureError(f"fixture index missing: {index_path}")
        raw = index_path.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        if digest != PINNED_FIXTURE_INDEX_SHA256:
            raise DemoFixtureError("fixture index integrity check failed: sha256 mismatch")
        try:
            index = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise DemoFixtureError("fixture index is not valid UTF-8 JSON") from exc
        if not isinstance(index, dict) or not isinstance(index.get("fixtures"), list):
            raise DemoFixtureError("fixture index has an invalid schema")
        entries = index["fixtures"]
        seen_files: set[str] = set()
        seen_ids: set[str] = set()
        required = {
            "fixture_id", "file", "data_mode", "source", "collected_at", "agentguard_version",
            "agentguard_commit", "sanitized", "sha256", "capabilities", "not_provable",
        }
        for entry in entries:
            if not isinstance(entry, dict) or not required <= set(entry):
                raise DemoFixtureError("fixture index entry is missing required provenance fields")
            name = entry["file"]
            fixture_id = entry["fixture_id"]
            if (
                not isinstance(name, str) or Path(name).name != name or name in {"", ".", ".."}
                or not isinstance(fixture_id, str) or not fixture_id
                or name in seen_files or fixture_id in seen_ids
            ):
                raise DemoFixtureError("fixture index contains an unsafe or duplicate identity")
            if entry["data_mode"] not in {"recorded", "synthetic"}:
                raise DemoFixtureError(f"fixture {name} must be RECORDED or SYNTHETIC")
            if not entry["sanitized"] or not _SHA256_RE.fullmatch(str(entry["sha256"])):
                raise DemoFixtureError(f"fixture {name} has invalid sanitization or SHA-256 metadata")
            if not all(isinstance(entry[field], str) and entry[field].strip() for field in (
                "source", "collected_at", "agentguard_version", "agentguard_commit"
            )):
                raise DemoFixtureError(f"fixture {name} is missing source provenance")
            if not isinstance(entry["capabilities"], list) or not isinstance(entry["not_provable"], list):
                raise DemoFixtureError(f"fixture {name} has invalid capability or limitation metadata")
            seen_files.add(name)
            seen_ids.add(fixture_id)
        self._index = entries

    def fixture(self, name: str) -> dict:
        if name in self._cache:
            return self._cache[name]
        entry = next((item for item in self._index if item["file"] == name), None)
        if entry is None:
            raise DemoFixtureError(f"fixture not registered in index: {name}")
        root = self._dir.resolve()
        path = (root / name).resolve()
        try:
            path.relative_to(root)
        except ValueError as exc:
            raise DemoFixtureError("fixture file must stay inside the fixture directory") from exc
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
        for item in self._overlay.values():
            if item.get("request_id") not in {existing.get("request_id") for existing in items}:
                items.append(item)
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
        if request_id in self._overlay:
            return dict(self._overlay[request_id])
        details = self.fixture("investigations.json").get("details", {})
        item = details.get(request_id)
        return dict(item) if item else None

    def get_timeline(self, request_id: str) -> list[dict]:
        if request_id in self._overlay:
            item = self._overlay[request_id]
            events = [
                {"step": "created", "label": "调查创建", "status": "completed", "at": item.get("created_at")}
            ]
            # Only the creation step is confirmed for a demo-only submission;
            # every later step stays pending - nothing was actually run.
            for step, label in [
                ("validated", "请求验证"),
                ("capabilities", "能力检查"),
                ("planned", "审计计划"),
                ("submitted", "运行提交"),
                ("running", "运行中"),
                ("evidence", "证据生成"),
                ("completed", "调查完成"),
            ]:
                events.append({"step": step, "label": label, "status": "pending", "at": None})
            return events
        items = self.fixture("timeline.json")["items"]
        return [event for event in items if event.get("request_id") == request_id]

    def get_evidence(self, request_id: str) -> dict | None:
        items = self.fixture("evidence.json")["items"]
        return items.get(request_id)

    def list_evidence(self, *, request_id: str | None = None) -> list[dict]:
        items = list(self.fixture("evidence.json").get("items", {}).values())
        if request_id:
            items = [item for item in items if item.get("request_id") == request_id]
        return items

    def get_defense(self, request_id: str) -> dict | None:
        items = self.fixture("defense.json")["items"]
        return items.get(request_id)

    def list_defense_candidates(self, *, request_id: str | None = None) -> list[dict]:
        items = list(self.fixture("defense.json").get("items", {}).values())
        if request_id:
            items = [item for item in items if item.get("request_id") == request_id]
        return items

    # ------------------------------------------------------------------ #
    # interaction graph samples (B4)
    # ------------------------------------------------------------------ #
    def graph_sample(self, *, request_id: str | None) -> dict | None:
        graph = self.fixture("graph.json")
        # The fixed graph sample is scenario-scoped; request_id is accepted for
        # URL stability but does not imply per-run message fidelity.
        if request_id and graph.get("scenario_id") != "sc-qwb-001" and request_id not in graph.get("nodes", []):
            return None
        return graph

    def graph_samples(self) -> list[dict]:
        return [self.fixture("graph.json")]

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

    def get_findings(self, run_id: str) -> dict | None:
        items = self.fixture("findings.json").get("items", {})
        return items.get(run_id)

    def get_hypotheses(self, run_id: str) -> dict | None:
        items = self.fixture("hypotheses.json").get("items", {})
        return items.get(run_id)

    def get_investigation_journal(self, run_id: str) -> dict | None:
        items = self.fixture("investigation.json").get("items", {})
        return items.get(run_id)

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
