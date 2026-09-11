# 安装与复现

[返回首页](../README.md) · [实验结果](results.md) · [Windows 演练](simulator.md)

支持 Python 3.12 及以上；产生基准结果的版本见 [依赖快照](../requirements/validated-py312.txt)。

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements/validated-py312.txt
python -m pip install -e ".[research,dev]"
python -m pytest -q
python -m cumcm_b.benchmark --smoke --out .local/smoke
```

Windows 将激活命令换成 `.\.venv\Scripts\Activate.ps1`。`--smoke` 只使用内存中的 `SyntheticArena`，不连接官方模拟器。

完整复现：

```bash
python scripts/setup_quality_tools.py
python scripts/reproduce.py
```

程序依次执行环境检查、测试、106 局实验、数据剖析、14 张图生成、严格图形检查和四问覆盖检查，生成 [结果清单](../results/reproduction.json)。原版质量工具固定于 `tools/quality-tools.lock.json` 指定的提交，下载到 `.local/` 缓存并逐文件校验 SHA-256；主算法和最小测试不依赖该工具。

`results/synthetic/` 是逐局表，`reports/figures/` 是 SVG、300 dpi PNG 和灰度预览，`.local/reproduction/` 是不入库的控制台日志。另建隔离输出可执行 `python scripts/reproduce.py --base .local/review-run`；`--base` 必须位于仓库内。

基础种子为 `20260911…20260930`，压力种子为 `909`。主表 86 行、覆盖表 40 行含 20 行复用，合计 106 个独立运行。实际耗时、时间戳和请求 UUID 会随运行变化，不能用文件字节完全相等作为跨平台一致性标准。

图形命令：

```bash
python scripts/build_figures.py --results results/synthetic --out reports/figures
```

缺少中文字体时先安装 Noto Sans CJK SC 等系统字体。每图标注数据源及“本地合成/构造”边界。

质量检查和构建：

```bash
python -m ruff check src scripts tests
python -m ruff format --check src scripts tests
python -m build
```

CI 在 Ubuntu、Windows 上运行测试、合成烟雾测试、Ruff 和 wheel 构建，不启动官方会话。复现清单将原版工具生成的绝对路径规范化为仓库相对路径，同时保留文件哈希。
