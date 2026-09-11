# q3 优化讨论与当前实验

[返回首页](../README.md) · [模型](model.md) · [实验结果](results.md)

## 为什么先优化主动测角

q3 的七站覆盖证书已经保证全向源不会漏检，主要耗时来自覆盖站与定位点之间的移动，以及每个目标的主动测角。当前 `candidate_points` 对候选点计算多个假设位置的线性化定位误差，再加移动惩罚。

已有实现用所有假设位置中的最大误差排序，过度受保守外包多边形的人工顶点影响。新策略 `adaptive_q25` 保留同一候选集、同一有界误差模型和同一 MEC 安全停止条件，只把排序误差换成候选情形的 25% 分位数：

$$S(q)=Q_{0.25}\{U(q,g):g\in\mathcal G\}+\lambda\|q-p_{\rm cur}\|,\qquad \lambda=0.04.$$

`U` 仍是线性化误差代理，不能当作严格误差界；最终是否清除始终由保守半平面交集和最小包围圆半径 ≤ 19.75 m 决定。策略还保留 `adaptive`、`adaptive_p90` 和 `adaptive_median`，便于消融比较。

## 动态 q10：先控路程，再追求信息

进一步把主动测量分成两个阶段，形成 `adaptive_q10_dynamic`。对一个刚被发现、只有一条方向观测的信道，首次主动点使用较大的移动惩罚 λ=0.50；已有多条观测后，切换到 q10 误差和 λ=0.02。这样做的含义是先用近点获得第二条独立几何约束，再在收敛阶段追求信息增益。每次测量仍只使用当前 belief，清除仍必须通过 MEC 半径 ≤19.75 m 证书。

## 文献与开源项目如何转化

- Vander Hook、Tokekar、Isler 的主动 bearing-only 定位工作强调谨慎贪心、测量时间与移动时间联合代价。我们将它转成候选点评分，最后仍用有界误差集合认证。
- Tokekar 与 Isler 的有界测角误差工作支持“测量锥交集 + 最坏误差评估”的主框架；不能用高斯 FIM 替换保守几何判据。
- Song 等人的时空概率占据栅格适合间歇发射源，但本题反馈只有方向、near、no_signal。当前只借鉴事件后重排，不把暂时 no_signal 直接当作频道不存在。
- Doğançay 的 FIM 适合连续航点重规划。它可以作为未来候选排序的辅助项；题面是有界误差，FIM 只能作启发式。
- [`Coverage_Mission_Plannin`](https://github.com/GradualScholar/Coverage_Mission_Plannin) 的两阶段覆盖与动态重分配结构可借鉴；多 UAV 的 NSGA-II、拍卖和深度强化学习不直接移植到单机器人 q3。

## 当前对照

```bash
python scripts/benchmark_q3_optimization.py --seeds 50 --out .local/q3-optimization
```

脚本 `scripts/benchmark_q3_strategies.py` 在同一批 50 个固定合成种子上配对运行多种策略，不访问官方模拟器。主比较为：

| 策略 | 平均秒/源 | 相对基线 | 胜局 | 兜底动作 |
| --- | ---: | ---: | ---: | ---: |
| `adaptive` | 417.72 | — | — | 0 |
| `adaptive_q25` | 351.34 | −15.89% | 50/50 | 0 |
| `adaptive_q10` | 356.07 | −14.76% | 50/50 | 0 |
| `adaptive_q10_dynamic` | **333.75** | **−20.10%** | 50/50 | 0 |

把角度候选细化到 11.25° 的 `adaptive_q25_fine` 在同一批种子上为 345.98 秒/源（−17.18%）；但把细化角度与动态 q10 叠加反而在 20 局复核中为 349.13 秒/源，说明候选点加密并不与每种信息目标相容，已保留为消融结果而非默认方案。

在完全分离的 50 个验证种子（20261011–20261060）上，动态策略为 322.62 秒/源，18/50 局低于 300 秒/源，仍全部完成且无兜底。这说明它是一个值得保留的离线候选，但不能覆盖完整官方策略组的 q25 结论；300 秒/源也不应写成已达到的成绩。

## 当前版本选择

完整 Windows 官方策略组汇总见 [`q3_official_strategy_summary_20260911.csv`](../results/practice/q3_official_strategy_summary_20260911.csv)，说明见 [`q3_official_practice_report_20260911.md`](../reports/q3_official_practice_report_20260911.md)。25 局记录全部完整退出，另有 3 个目录缺少 `summary.json`。由于不同策略没有使用共同隐藏场景，且源数量 N 在 10–16 间变化，官方演练只能验证协议、证书和日志，不能承担策略排序。

当前选型回到同源配对的本地合成实验。`scripts/benchmark_q3_strategies.py` 在 50 个相同种子上比较，完整逐局结果见 [`q3_strategy_comparison/runs.csv`](../results/synthetic/q3_strategy_comparison/runs.csv)，摘要见 [`q3_strategy_comparison/summary.json`](../results/synthetic/q3_strategy_comparison/summary.json)。所有策略均完整且无兜底：

| 策略 | 平均秒/源 | 相对 `adaptive` | 胜局 |
| --- | ---: | ---: | ---: |
| `adaptive_q10_dynamic` | **333.75** | **−20.10%** | 50/50 |
| `adaptive_q25` | 351.34 | −15.89% | 50/50 |
| `adaptive_q10` | 356.07 | −14.76% | 50/50 |
| `adaptive` | 417.72 | — | — |

因此当前 q3 入口改为 `adaptive_q10_dynamic`：首次主动点提高移动惩罚，后续测量再追求 q10 信息增益；MEC ≤19.75 m 才允许清除的证书和光学兜底不变。官方 25 局中 q25 的原始单源均值较低，主要受各组 N 分布和覆盖固定开销混淆，不能推翻同源配对结论。

细角度、概率栅格和 q25 动态组合保留为消融，不进入入口。安全边界保持不变：不以 FIM 或概率模型替代有界误差几何证书，也不把本地均值写成正式成绩。

贝叶斯占据栅格、覆盖站一阶前瞻和目标 TSP/2-opt 的独立消融均未优于 q25，详见 [`optimization_belief_grid.md`](optimization_belief_grid.md) 与脚本；这些负结果说明继续堆叠复杂全局优化并不能自动降低移动距离。

任何新批次继续报告完整率、移动距离、测量次数、换频次数和兜底次数，并优先使用同一批源配置进行策略对照。q4 当前优化方案见 [q4 优化与联合巡回](q4_optimization.md)。
