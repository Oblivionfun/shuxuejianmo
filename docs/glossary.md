# B 题术语与符号

| 中文 | 英文 | 符号 | 定义 | 单位 | 首次出现 | 禁止混用 |
|---|---|---|---|---|---|---|
| 目标区域 | target domain | Ω | 半径 1800 m 的闭圆盘 | m²（区域） | 报告 §1 | 机器狗活动限制区域 |
| 干扰源位置 | source position | g | 未知固定二维坐标 | m | §1 | 检测点 p |
| 检测点 | sensing location | p_i | 第 i 次检测坐标 | m | §4 | 源位置 |
| 示向度 | measured bearing | θ_i | 接口 svd_deg，东向为零，逆时针 | °，运算用 rad | §3 | 精确方位角、距离 |
| 误差界 | angular error bound | ε | 题面 1°；接口实现 1.01° | °/rad | §3 | 标准差、置信度 |
| 有效接收半径 | reception radius | R | 源自身接收距离上限，1000–1500 | m | §1 | 清除半径、定位半径 |
| 定向方向 | emission orientation | d | 未知发射半平面的单位法向 | 无量纲 | §7 | 从检测点指向源的示向度 |
| 测向楔形 | bearing wedge | W_i | 两个有向半平面交 | 区域 | §4.1 | 无向直线带 |
| 纯交会区域 | bearing intersection | P | 所有 W_i 的交，可空、无界或退化 | 区域 | §4.1 | 加入圆盘先验后的区域 |
| 保守外包 | conservative outer region | P_out | 包含全部真可行位置的凸多边形 | 区域 | §4.1 | 内接近似、精确曲边区域 |
| 区域直径 | region diameter | D | 区域最大点对距离 | m | §4.2 | 最小包围圆直径 |
| 最小包围圆 | minimum enclosing circle | (c*,R*) | 覆盖全可行集的最小半径圆 | m | §4.3 | 直径端点中点圆 |
| 近距离反馈 | near response | near | 有信号且源距检测点≤5 m | 布尔事件 | §1/8 | 无信号 |
| 清除半径 | clearing radius | r_clear | 光学/激光可清除距离 20 m | m | §4.3 | 接收半径 |
| 安全候选区 | guaranteed-reception region | C_safe | 到所有可能源距离≤1000 m 的点集 | 区域 | §5 | 定向源保证可见区 |
| 方位导数 | bearing Jacobian | h_i,H | 方位函数对源坐标的一阶导数 | rad/m | §5 | 真实后验误差 |
| 线性化评分 | linearized error proxy | U | ε 乘伪逆各列范数之和 | m | §5 | 严格误差界、置信区间 |
| 路程权重 | travel penalty | λ | 默认 0.02，候选评分参数 | m/m | §5 | 官方评分权重 |
| 干扰源数量 | source count | N | 10–16，运行时未知 | 个 | §1 | 已发现数、已清除数 |
| 频道 | channel | k | 整数 1–20，每频道至多一源 | 无量纲 | §1 | 目标序号 |
| 当前测向频道 | current receiver channel | k_current | 仅由成功 /measure 改变 | 无量纲 | §8 | /clear 的目标频道 |
| 累计虚拟时间 | virtual elapsed time | T | 移动、切换、检测、清除成本之和 | s | §8 | 现实运行时间 |
| 现实运行时间 | wall-clock runtime | t_real | /enter 到结束实际程序耗时 | s | §8 | 虚拟时间 |
| 平均定位清除时间 | mean localization/clearing time | T/N_clear | 全局总虚拟时间除以清除数 | s/个 | §9 | 仅清除动作时间均值 |
| 完成证书 | completion certificate | certificate | 覆盖完成且发现源均已清除，或已清除 16 源 | 逻辑值 | §6 | 长期未发现、正常退出 |
| 本地合成实验 | local synthetic experiment | origin=synthetic | 根据题面自行构造环境 | 标签 | §9 | 官方演练、正式成绩 |
| 幂等键 | idempotency key | request_id | 新动作唯一，原动作重试保持原 ID 与内容 | 字符串 | §8 | 自增后重试 |
