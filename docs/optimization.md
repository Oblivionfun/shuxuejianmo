# q3 优化讨论与当前实验

[返回首页](../README.md) · [模型](model.md) · [实验结果](results.md)

## 为什么先优化主动测角

q3 的七站覆盖证书已经保证全向源不会漏检，主要耗时来自覆盖站与定位点之间的移动，以及每个目标的主动测角。当前 `candidate_points` 对候选点计算多个假设位置的线性化定位误差，再加移动惩罚。

已有实现用所有假设位置中的最大误差排序，过度受保守外包多边形的人工顶点影响。新策略 `adaptive_q25` 保留同一候选集、同一有界误差模型和同一 MEC 安全停止条件，只把排序误差换成候选情形的 25% 分位数：

$$S(q)=Q_{0.25}\{U(q,g):g\in\mathcal G\}+\lambda\|q-p_{\rm cur}\|,\qquad \lambda=0.04.$$

`U` 仍是线性化误差代理，不能当作严格误差界；最终是否清除始终由保守半平面交集和最小包围圆半径 ≤ 19.75 m 决定。策略还保留 `adaptive`、`adaptive_p90` 和 `adaptive_median`，便于消融比较。

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

脚本在同一批种子上配对运行 `adaptive`（基线，λ=0.02）与 `adaptive_q25`（λ=0.04），不访问官方模拟器。50 个固定合成种子得到 417.72 → 351.34 秒/源，降低 15.89%，候选策略 50/50 局更快且全部完成；这还没有达到 300 秒/源，也不是官方测试集。

下一步应在未参与调参的种子上做 50–100 局验证，并报告完整率、移动距离、测量次数、换频次数和兜底次数。如果低分位目标退化，应回退到 `adaptive` 或采用分位数与最坏误差的混合评分。

当前 q3 官方演练入口默认使用 `adaptive_q25`，q4 仍默认 `adaptive`；连接前仍需人工确认模拟器界面为演练。正式测试和论文结论不会自动由此实验填充。
