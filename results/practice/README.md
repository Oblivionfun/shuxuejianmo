# 官方演练汇总

`summary.csv` 是已完成官方**演练**的匿名逐局汇总，不是正式成绩。原始加密日志、界面观察和队伍识别信息仅保留在本机归档，不进入 Git。

字段中的 `official_total_sources` 是演练结束页记录的源总数；客户端运行时并不知道它。`policy_sha256` 用于确认 7 局使用同一套策略源码，`scenario_origin` 固定为 `official_practice`。请结合 [结果说明](../../docs/results.md) 阅读，不能用这 7 局推算奖项、排名或正式成功率。

完整策略组使用 [`q3_official_strategy_summary_20260911.csv`](q3_official_strategy_summary_20260911.csv)，配套说明为 [`q3_official_practice_report_20260911.md`](../../reports/q3_official_practice_report_20260911.md)。它汇总 25 个完整 `summary.json`，并明确列出 3 个缺失汇总的目录；主策略选择按合并单源时间和清除数共同判断，不按总虚拟时间单指标排序。
