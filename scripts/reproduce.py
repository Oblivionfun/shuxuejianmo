"""Reproduce local experiments and figures with the pinned upstream quality tools."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

from quality_tools import ROOT, load_tool, resolve_tools, tool_lock


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base", type=Path, help="isolated output directory inside this repository"
    )
    args = parser.parse_args()
    base = (ROOT / args.base).resolve() if args.base else ROOT
    if not base.is_relative_to(ROOT):
        parser.error("--base must stay inside the repository")
    skill = resolve_tools()
    role = skill / "references/roles/编程手/scripts"
    result = base / "results/synthetic"
    figures = base / "reports/figures"
    audit = base / ".local/reproduction"
    audit.mkdir(parents=True, exist_ok=True)
    commands = [
        (
            "environment",
            [str(role / "check_env.py"), "--features", "data", "visualization", "optimization"],
        ),
        ("tests", ["-m", "pytest", "-q", "tests"]),
        ("benchmark", ["-m", "cumcm_b.benchmark", "--cases", "20", "--out", str(result)]),
        (
            "profile",
            [
                str(skill / "tools/figure/scripts/profile_data.py"),
                str(result / "runs.csv"),
                "--group",
                "question",
                "--group",
                "strategy",
                "--json",
            ],
        ),
        ("figures", ["scripts/build_figures.py", "--results", str(result), "--out", str(figures)]),
        (
            "figure-format",
            [
                str(skill / "tools/figure/scripts/check_figure.py"),
                str(figures / "*.png"),
                str(figures / "*.svg"),
                str(figures / "_qa/*.png"),
                "--strict",
            ],
        ),
        (
            "figure-coverage",
            [
                str(role / "figure_audit.py"),
                str(figures),
                "--questions",
                "q1",
                "q2",
                "q3",
                "q4",
                "--strict",
            ],
        ),
    ]
    receipts = []
    env = dict(os.environ, PYTHONUTF8="1", MPLBACKEND="Agg")
    for i, (name, arguments) in enumerate(commands, start=1):
        print(f"[{i}/{len(commands)}] {name}", flush=True)
        done = subprocess.run(
            [sys.executable, *arguments],
            cwd=ROOT,
            env=env,
            text=True,
            encoding="utf-8",
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        log = audit / f"{i:02d}-{name}.log"
        log.write_text(done.stdout, encoding="utf-8")
        receipts.append({"step": name, "returncode": done.returncode})
        (audit / "steps.json").write_text(json.dumps(receipts, indent=2) + "\n", encoding="utf-8")
        if done.returncode:
            print(done.stdout[-6000:])
            return done.returncode

    inputs = [
        ROOT / path
        for path in (
            "pyproject.toml",
            "requirements/validated-py312.txt",
            "tools/quality-tools.lock.json",
            "docs/model.md",
            "docs/glossary.md",
            "docs/problem-inputs.json",
        )
    ]
    for directory in ("src/cumcm_b", "scripts", "tests"):
        inputs.extend(sorted((ROOT / directory).glob("*.py")))
    inputs.extend(skill / name for name in tool_lock()["files"])
    manifest_tool = load_tool(
        "cumcm_repro_manifest", "references/roles/编程手/scripts/repro_manifest.py"
    )
    manifest = manifest_tool.build_manifest(
        inputs=inputs,
        seed=20260911,
        parameters={
            "base_seeds": list(range(20260911, 20260931)),
            "stress_seed": 909,
            "local_not_official": True,
            "error_deg": 1.01,
            "circle_sides": 128,
            "clear_margin_radius_m": 19.75,
            "optical_grid_step_m": 25,
            "travel_weight": 0.02,
            "max_active_measurements": 6,
            "q4_legacy_coverage": "triangular_legacy",
            "q4_legacy_triangle_side_m": 950,
            "q4_legacy_triangle_shift": [1 / 3, 1 / 3],
            "q4_current_policy": "q4_joint",
            "q4_current_coverage": "ring25",
            "q4_ring25_outer_sides": 16,
            "q4_ring25_inner_sides": 8,
            "q4_ring25_inner_radius_m": 997,
            "q4_ring25_outer_margin_m": 1,
            "q4_current_triangle_side_m": 995,
            "q4_current_triangle_shift": [0.23, 0.90],
            "q4_current_objective": "q10",
            "q4_current_final_order": "tsp",
            "q4_current_known_measure_budget": 3,
            "q4_defer_midroute_localization": True,
            "square_baseline_step_m": 600,
            "total_local_runs": 106,
        },
        command="python scripts/reproduce.py",
        packages=[
            "numpy",
            "scipy",
            "shapely",
            "requests",
            "pandas",
            "matplotlib",
            "seaborn",
            "pytest",
        ],
    )
    # Preserve upstream hashes; replace private absolute paths by documented logical paths.
    for item in manifest["input_files"]:
        path = Path(item["path"])
        item["path"] = (
            "quality-tools/" + path.relative_to(skill).as_posix()
            if path.is_relative_to(skill)
            else path.relative_to(ROOT).as_posix()
        )
    manifest["path_convention"] = (
        "Repository-relative; quality-tools/ resolves through tools/quality-tools.lock.json."
    )
    manifest["upstream_generator"] = {
        "repository": tool_lock()["repository"],
        "commit": tool_lock()["commit"],
        "path_only_normalization": True,
    }
    manifest["steps"] = receipts
    manifest["output_files"] = [
        {
            "path": path.relative_to(base).as_posix(),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "bytes": path.stat().st_size,
        }
        for directory in (result, figures)
        for path in sorted(directory.rglob("*"))
        if path.is_file()
    ]
    output = base / "results/reproduction.json"
    output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        f"Complete: {result.relative_to(ROOT)}; {figures.relative_to(ROOT)}; {output.relative_to(ROOT)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
