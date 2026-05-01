from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast


@dataclass(frozen=True)
class ManifestReplayReport:
    runtime_id: str
    candidate_id: str
    approved: bool
    reasons: list[str]
    success_rate_delta: float | None
    current_summary: dict[str, Any]
    candidate_summary: dict[str, Any]


def _read_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("expected JSON object")
    return cast(dict[str, Any], data)


def replay_manifest(manifest_path: Path) -> ManifestReplayReport:
    manifest = _read_json(manifest_path)

    if manifest.get("kind") != "promotion_manifest":
        raise ValueError("not a promotion_manifest")

    runtime_id = str(manifest["runtime_id"])
    candidate_id = str(manifest["candidate_id"])

    artifacts = manifest.get("artifacts") or {}
    cur_path = artifacts.get("current_summary")
    cand_path = artifacts.get("candidate_summary")
    dec_path = artifacts.get("decision")

    if not cur_path or not cand_path or not dec_path:
        raise ValueError("manifest missing required artifact references")

    cur_payload = _read_json(Path(cur_path))
    cand_payload = _read_json(Path(cand_path))
    dec_payload = _read_json(Path(dec_path))

    cur_summary = dict(cur_payload.get("summary") or {})
    cand_summary = dict(cand_payload.get("summary") or {})

    decision = dict(dec_payload.get("decision") or {})
    approved = bool(decision.get("approved", False))
    reasons = list(decision.get("reasons") or [])

    deltas = dict(decision.get("deltas") or {})
    sr_delta = deltas.get("success_rate_delta")
    success_rate_delta = float(sr_delta) if isinstance(sr_delta, (int, float)) else None

    return ManifestReplayReport(
        runtime_id=runtime_id,
        candidate_id=candidate_id,
        approved=approved,
        reasons=reasons,
        success_rate_delta=success_rate_delta,
        current_summary=cur_summary,
        candidate_summary=cand_summary,
    )


def report_to_markdown(report: ManifestReplayReport) -> str:
    lines: list[str] = []
    lines.append("# Promotion Replay")
    lines.append("")
    lines.append(f"- runtime_id: `{report.runtime_id}`")
    lines.append(f"- candidate_id: `{report.candidate_id}`")
    lines.append(f"- approved: `{report.approved}`")
    lines.append(f"- reasons: `{report.reasons}`")
    lines.append(f"- success_rate_delta: `{report.success_rate_delta}`")
    lines.append("")
    lines.append("## Current summary")
    lines.append("```json")
    lines.append(json.dumps(report.current_summary, ensure_ascii=False, indent=2))
    lines.append("```")
    lines.append("")
    lines.append("## Candidate summary")
    lines.append("```json")
    lines.append(json.dumps(report.candidate_summary, ensure_ascii=False, indent=2))
    lines.append("```")
    lines.append("")
    return "\n".join(lines)