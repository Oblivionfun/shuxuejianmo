"""Create a fresh standalone Windows practice bundle without touching existing sessions."""

import argparse
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", required=True, type=Path)
    args = parser.parse_args()
    destination = args.destination.expanduser().resolve()
    if destination.exists():
        parser.error("destination already exists; choose a new directory")
    destination.mkdir(parents=True)
    shutil.copytree(
        ROOT / "src/cumcm_b",
        destination / "cumcm_b",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    shutil.copytree(
        ROOT / "tests", destination / "tests", ignore=shutil.ignore_patterns("__pycache__", "*.pyc")
    )
    for name in ("requirements", "docs"):
        (destination / name).mkdir()
    shutil.copy2(
        ROOT / "requirements/validated-py312.txt", destination / "requirements/validated-py312.txt"
    )
    shutil.copy2(ROOT / "docs/simulator.md", destination / "docs/simulator.md")
    (destination / "run_practice.py").write_text(
        '"""Manual practice-session entry point."""\nfrom cumcm_b.practice import main\n\n'
        'if __name__ == "__main__":\n    raise SystemExit(main())\n',
        encoding="utf-8",
    )
    (destination / "README.md").write_text(
        "# Windows 演练工作台\n\n"
        "在本目录使用 Windows Python 3.12。此导出不启动模拟器会话。\n\n"
        "```powershell\npython -m pip install -r requirements/validated-py312.txt\n"
        "python -m pytest -q\npython run_practice.py --help\n```\n\n"
        "确认界面为演练且填写当前演练 robot_id 后，按 docs/simulator.md 操作。"
        "全部逐动作日志输出到 .local/practice/；正式模式未经授权。\n",
        encoding="utf-8",
    )
    files = {
        path.relative_to(destination).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(destination.rglob("*"))
        if path.is_file()
    }
    (destination / "bundle-manifest.json").write_text(
        json.dumps({"sha256": files}, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Exported {len(files)} files to {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
