# 工具来源与引用

| 来源 | 用途 |
| :--- | :--- |
| 用户提供的 B 题题面与两个附件，[输入登记](problem-inputs.json) | 物理条件、计时规则与四动作协议 |
| Toussaint, *Solving geometric problems with the rotating calipers*, MELECON 1983，[作者出版物页](https://cgm.cs.mcgill.ca/~godfried/publications.html) | 凸多边形直径的旋转卡壳思路 |
| Welzl, *Smallest enclosing disks*, LNCS 555, 1991，[作者原文](https://people.inf.ethz.ch/emo/PublFiles/SmallEnclDisk_LNCS555_91.pdf) | 最小包围圆随机增量思路 |
| Zhao, Chen, Lee, *Optimal placement of bearing-only sensors*, ACC 2012，[DOI](https://doi.org/10.1109/ACC.2012.6314884) | 角度几何选点启发，不直接套用其统计最优结论 |

七站、三角网格、光学兜底和计时整合是本项目在 [模型文档](model.md) 中的直接推导，文献不构成本算法已被外部验证的证据。

建模、编程及独立质检流程使用 [XiaoMaColtAI/math-modeling-skill](https://github.com/XiaoMaColtAI/math-modeling-skill)，固定提交 `3527fad922660397834a6167fc2b4c29ee64ba17`。原版绘图与检查脚本按 [工具锁文件](../tools/quality-tools.lock.json) 下载并逐文件验证，未复制进仓库。NumPy、SciPy、Shapely、Requests、pandas、Matplotlib、Seaborn、Pillow、pytest、Ruff、build 的版本见 [依赖快照](../requirements/validated-py312.txt)。

持续集成依照 [actions/checkout](https://github.com/actions/checkout) 与 [actions/setup-python](https://github.com/actions/setup-python) 的官方用法。第三方库与工具各自保留上游许可，本仓库不替其追加授权声明。
