"""Generate demo/fixtures/index.json with SHA-256 provenance for every fixture.

Run from the repo root:
    python demo/scripts/make_fixture_index.py

The demo service verifies each fixture's hash against this index on load, so
editing a fixture without regenerating the index fails loudly.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES_DIR = REPO_ROOT / "demo" / "fixtures"
INDEX_PATH = FIXTURES_DIR / "index.json"

AGENTGUARD_COMMIT = "00d12bee352060ea6014eebea8400edd7c74a029"

FIXTURE_META: dict[str, dict] = {
    "scenarios.json": {
        "fixture_id": "fx-scenarios-001",
        "data_mode": "synthetic",
        "source": "generated for QWB demo",
        "sanitized": True,
        "capabilities": ["scenario browsing"],
        "not_provable": ["场景不构成真实威胁环境复现。"],
    },
    "investigations.json": {
        "fixture_id": "fx-inv-001",
        "data_mode": "recorded",
        "source": "sanitised recording from AgentGuard A7 contract tests",
        "sanitized": True,
        "capabilities": ["investigations.list", "investigations.detail"],
        "not_provable": ["调查状态不代表真实 WARDEN 运行。"],
    },
    "timeline.json": {
        "fixture_id": "fx-timeline-001",
        "data_mode": "recorded",
        "source": "derived from recorded investigation states",
        "sanitized": True,
        "capabilities": ["investigations.timeline"],
        "not_provable": ["事件时间为录制值，不能作为真实运行时间线。"],
    },
    "evidence.json": {
        "fixture_id": "fx-evidence-001",
        "data_mode": "recorded",
        "source": "sanitised governed evidence samples",
        "sanitized": True,
        "capabilities": ["evidence.view"],
        "not_provable": ["causal_validated 结论仅在录制样例受控条件下成立。"],
    },
    "defense.json": {
        "fixture_id": "fx-defense-001",
        "data_mode": "recorded",
        "source": "sanitised defense preview samples",
        "sanitized": True,
        "capabilities": ["defense.preview", "defense.view"],
        "not_provable": ["防御候选从未执行；execution_supported 恒为 false。"],
    },
    "graph.json": {
        "fixture_id": "fx-graph-001",
        "data_mode": "synthetic",
        "source": "fixed teaching graph for interaction visualisation",
        "sanitized": True,
        "capabilities": ["interaction.graph.demo"],
        "not_provable": ["图谱边不代表真实消息级传输；风险分级为演示标注。"],
    },
    "experiments.json": {
        "fixture_id": "fx-experiments-001",
        "data_mode": "recorded",
        "source": "sanitised experiment comparison records",
        "sanitized": True,
        "capabilities": ["experiments.compare"],
        "not_provable": ["budget 数值为演示记录，不代表真实成本。"],
    },
    "experiences.json": {
        "fixture_id": "fx-experiences-001",
        "data_mode": "recorded",
        "source": "sanitised verified experience records",
        "sanitized": True,
        "capabilities": ["experiences.read"],
        "not_provable": ["演示经验不得用于真实因果实验统计。"],
    },
    "reports.json": {
        "fixture_id": "fx-reports-001",
        "data_mode": "recorded",
        "source": "derived from recorded investigation results",
        "sanitized": True,
        "capabilities": ["reports.read", "reports.export"],
        "not_provable": ["报告指标与源数据一致，不推断新的因果结论。"],
    },
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    collected_at = datetime.now(UTC).isoformat()
    index: dict = {
        "schema_version": "0.1",
        "agentguard_commit": AGENTGUARD_COMMIT,
        "agentguard_version": "0.1.0-a7",
        "collected_at": collected_at,
        "fixtures": [],
    }
    missing = [name for name in FIXTURE_META if not (FIXTURES_DIR / name).is_file()]
    if missing:
        raise SystemExit(f"missing fixture files: {missing}")
    for name, meta in FIXTURE_META.items():
        index["fixtures"].append(
            {
                "fixture_id": meta["fixture_id"],
                "file": name,
                "data_mode": meta["data_mode"],
                "source": meta["source"],
                "collected_at": collected_at,
                "agentguard_version": index["agentguard_version"],
                "agentguard_commit": AGENTGUARD_COMMIT,
                "sanitized": meta["sanitized"],
                "sha256": sha256_file(FIXTURES_DIR / name),
                "capabilities": meta["capabilities"],
                "not_provable": meta["not_provable"],
            }
        )
    INDEX_PATH.write_text(json.dumps(index, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {INDEX_PATH} with {len(index['fixtures'])} fixtures")


if __name__ == "__main__":
    main()
