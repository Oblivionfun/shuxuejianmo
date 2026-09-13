# Q4 ring25 配对实验

- 来源：本地 `SyntheticArena`，不是官方成绩。
- 种子：`20261011`--`20261060`，四种方案使用同一批源配置。
- 运行：`.venv/bin/python scripts/benchmark_q4_optimization.py --seeds 50 --start 20261011 --out results/synthetic/q4_optimization_ring25`
- 关键文件：`runs.csv` 为逐局结果，`summary.json` 为汇总。
- 完整性：200 局均 `completion_certificate=true` 且 `exit_ok=true`。
- 主结论：`ring25_q4_joint` 平均 `587.9702 s/源`，相对 `optimized_q4_joint` 平均降低 `15.3910%`；这只是配对合成证据，需用新的官方演练会话复核。
