"""Run inside Windows after manually starting an OFFICIAL PRACTICE session."""

import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
import os
import platform
import sys
import time
from cumcm_b.protocol import HttpTransport, RobotClient
from cumcm_b.policy import CoveragePolicy


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--robot-id", default=os.environ.get("CUMCM_ROBOT_ID"))
    parser.add_argument("--question", type=int, choices=[3, 4], required=True)
    parser.add_argument(
        "--coverage",
        choices=["triangular", "square"],
        default="triangular",
        help="question 4 coverage; question 3 always uses seven stations",
    )
    parser.add_argument("--base-url", default="http://127.0.0.1:2026")
    parser.add_argument(
        "--practice-ready",
        action="store_true",
        help="confirm the UI currently shows a ready PRACTICE session",
    )
    parser.add_argument(
        "--output-dir", type=Path, help="new private output directory; must not already exist"
    )
    parser.add_argument(
        "--strategy",
        choices=[
            "adaptive",
            "adaptive_p90",
            "adaptive_q10",
            "adaptive_q10_dynamic",
            "adaptive_q10_dynamic_fine",
            "adaptive_q25",
            "adaptive_q25_fine",
            "adaptive_median",
        ],
        help="q3 defaults to adaptive_q25; q4 defaults to adaptive",
    )
    args = parser.parse_args()
    if not args.robot_id or not args.practice_ready:
        parser.error("supply robot ID and --practice-ready after checking the simulator UI")
    out = args.output_dir or Path(".local/practice") / time.strftime("%Y%m%d-%H%M%S")
    out.mkdir(parents=True, exist_ok=False)
    root = Path(__file__).resolve().parent
    sources = sorted(root.glob("*.py"))
    snapshot = {
        "python": sys.version,
        "platform": platform.platform(),
        "packages": {
            p: importlib.metadata.version(p) for p in ("numpy", "scipy", "shapely", "requests")
        },
        "question": args.question,
        "coverage": args.coverage if args.question == 4 else "seven",
        "practice_ready_is_manual_confirmation": True,
        "sha256": {
            str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources
        },
    }
    (out / "provenance.json").write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    client = RobotClient(
        HttpTransport(args.base_url), args.robot_id, log_path=out / "actions.jsonl"
    )
    strategy = args.strategy or ("adaptive_q25" if args.question == 3 else "adaptive")
    weight = 0.04 if strategy in {"adaptive_q25", "adaptive_q25_fine"} else 0.02
    if strategy == "adaptive_q10_dynamic":
        weight = 0.02
    policy = CoveragePolicy(
        client, args.question, strategy=strategy, travel_weight=weight, coverage=args.coverage
    )
    result = policy.run()
    result["scenario_origin"] = "official_practice_user_selected_not_api_verified"
    result["total_sources"] = None
    (out / "summary.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["completion_certificate"] and result["exit_ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
