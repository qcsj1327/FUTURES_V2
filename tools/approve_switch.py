from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from app.orchestration.strategy_switch import write_strategy_switch_approved


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected json object: {path}")
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="approve_switch",
        description="Approve a strategy switch proposal artifact.",
    )
    parser.add_argument("proposal_path", type=str)
    parser.add_argument("--output", type=str, required=True)
    args = parser.parse_args(argv)

    proposal_path = Path(args.proposal_path)
    proposal = _read_json(proposal_path)
    proposal["path"] = str(proposal_path)
    out = write_strategy_switch_approved(
        proposal=proposal,
        output_path=Path(args.output),
    )
    print(json.dumps({"approved_path": str(out)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
