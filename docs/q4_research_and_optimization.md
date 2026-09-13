# q4 外部方法检索与采用边界

本页记录本轮公开资料检索，以及哪些思想被转化为本项目的可审计改动。外部方法只提供算法启发，不能替代题目接口约束和本地/官方演练证据。

## 参考项目与论文

| 资料 | 可借鉴内容 | 本项目的使用方式 |
| --- | --- | --- |
| [Fields2Cover](https://github.com/Fields2Cover/Fields2Cover) | 将覆盖分解、路线优化和可行转向拆成模块，并支持 OR-Tools 路线优化 | 保留三角形覆盖证明；用确定性开放路径和 2-opt 优化站点/目标访问顺序，没有直接替换为黑盒覆盖器 |
| [OpenNav Coverage](https://github.com/open-navigation/opennav_coverage) | 将完整覆盖任务拆成 headland、swath、route、path 四层 | 采用“覆盖单元—站点路线—末端清除”分层，保留本题的接口安全证书 |
| [CAP: Coverage Guidance Graph](https://arxiv.org/abs/2503.00647) | 在线维护覆盖引导图，减少路径重叠并支持未知环境重规划 | 作为后续在线重排的方向；当前主线先用确定性路线，避免把未知真值带入策略 |
| [Adaptive Coverage Path Planning](https://arxiv.org/abs/2302.03164) | 用有限视界树评估覆盖收益，体现信息增益的边际递减 | 支持“测量预算优先给最大 MEC”的 q4 站内调度；未直接使用其传感器模型 |
| [Adaptive Informative Path Planning](https://ojs.aaai.org/index.php/ICAPS/article/view/6645) | POMDP、动作剪枝和移动—传感代价联合规划 | 为 q10 候选评分和末端开放路径排序提供方法依据；严格清除证书仍由本题几何判据控制 |
| [SISL InformativePathPlanning](https://github.com/sisl/InformativePathPlanning) | 以信息增益作为节点奖励，按序构造路径并处理自适应目标 | 将 q4 测向候选点的排序从单纯最坏半径改为 `q10` 代理；不把代理当严格误差上界 |
| [CMU Active range and bearing localization](https://publications.ri.cmu.edu/active-range-and-bearing-based-radiation-source-localization) | 根据 Fisher 信息选择下一航点，并允许步长随信息在线变化 | 保留现有有界楔形/最小包围圆证书；只在证书安全的前提下用于候选测点排序 |
| [Sparse signal measurements from UGVs](https://arxiv.org/abs/2312.03493) | 用稀疏覆盖轨迹收集信息，减少回溯和重复探索 | 支持“覆盖阶段先收集信息、末段统一清除”的两阶段结构；本题仍需完成定向源覆盖证书，不能照搬 RSSI 网格假设 |
| [ETH polygon coverage planning](https://github.com/ethz-asl/polygon_coverage_planning) | 多边形覆盖、分解和 GTSP 路线规划 | 用作路线优化的对照资料；本题固定圆域和定向半平面条件更适合保留显式三角剖分证明 |

## 本轮实验结论

- 官方演练第二局出现同一频道 79 次 `/clear`、其中 78 次 `no_target_in_range`。因此默认 q4 不再在覆盖巡回的每个站点触发未收敛目标的光学回退。
- 20 局复核中，`q10 + λ=0.02` 比 `worst + λ=0.04` 更快；50 局配对中，26 站联合 `q4_joint` 的均值为 **695.69 s/源**，49/50 局优于 26 站局部基线，全部完成并正常退出。
- 本轮将覆盖几何改为 `ring25`，并将沿途已发现频道的补充测量预算从 4 调整为 3：50 个共同种子全部完成，均值降至 **587.22 s/源**，相对 26 站联合策略降低 **15.59%**；平均移动距离由 35.07 km 降到 28.60 km，平均兜底动作由 15.58 降到 7.58。
- “只扫描前 10–12 个站点的未知频道”在本地测试可降到约 674 s/源，但只在约 70% 的局中清除全部真实源；这是漏源的协议风险，已排除出主线。
- “半径≤30 m 才途中处理”的 20 局组合均值约 685 s/源，优于完全延后的 689 s/源，但该策略仍需更多官方演练核验，默认入口暂不启用。

所有数字均为本地合成或用户选定的官方演练统计，不能解释为正式测试成绩或奖项预测。
