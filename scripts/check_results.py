"""Check the published result contract without rerunning the model."""

import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    summary = json.loads((ROOT / "results/synthetic/comparison_summary.json").read_text())
    validation = json.loads((ROOT / "results/synthetic/validation.json").read_text())
    assert summary["runs"] == validation["cases"] == 106
    assert summary["all_complete"] and validation["all_complete"]
    assert len(summary["paired_base_results"]) == 2
    assert summary["coverage_comparison"]["wins"] == 20
    assert 17.10 < summary["coverage_comparison"]["mean_reduction_percent"] < 17.12

    with (ROOT / "results/practice/summary.csv").open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 7
    assert sum(int(row["cleared"]) for row in rows) == 92
    assert all(row["scenario_origin"] == "official_practice" for row in rows)
    assert all(row["cleared"] == row["official_total_sources"] for row in rows)
    assert all(row["all_actions_accepted"] == "True" for row in rows)
    print("Published result contract: 106 local runs, 7 practice runs, 92/92 cleared.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
