# 工程迁移说明

整理日期：2026-09-11。原根目录材料已完整移动至本机 `.local/legacy-20260911/`，虚拟环境保留在 `.venv/`，移动没有删除原始文件；`migration_inventory.json` 记录清单，`.local/` 由 Git 忽略。

| 旧入口 | 新入口 |
| :--- | :--- |
| `cumcm_b/` | `src/cumcm_b/` |
| `experiments.py` | `src/cumcm_b/benchmark.py`，`cumcm-b-benchmark` |
| `run_official.py` | `src/cumcm_b/practice.py`，`cumcm-b-practice` |
| `reproduce.py` | `scripts/reproduce.py` |
| `make_figures.py` | `scripts/build_figures.py` |
| `题目分析报告.md` / `术语表格.md` | `docs/model.md` / `docs/glossary.md` |
| `阶段交付.md` | `docs/overview.md` |
| `results/local/` | `results/synthetic/` |
| `figures/` | `reports/figures/` |
| `requirements-lock.txt` | `requirements/validated-py312.txt` |
| `work/`、原题、安装包、视频、会话日志 | `.local/legacy-20260911/` 本机归档 |

几何、覆盖、选点和协议状态机保留；代码统一 Ruff 格式，命令行默认输出改到 `.local/`，增加依赖声明、复现、质量工具锁和 Windows 导出入口。历史回执中的旧绝对路径只对应归档原件；新工程的验证见 [验证记录](verification.md)。

下载目录的 `数学建模/B_workbench/` 与阶段交付包保持原样。候选 Git 工作台通过导出命令另建，避免覆盖已验证的 Windows 会话记录。
