# CUMCM 2026 B 项目代理工作约定

## 项目范围

- 本项目服务于全国大学生数学建模竞赛（CUMCM）2026 B 题，当前重点是问题 3、问题 4 的建模、算法优化、演练验证和论文材料整理。
- 所有结论必须能追溯到题目、代码、输入数据或实际运行日志。合成数据、固定随机种子和本地仿真结果必须明确标注为“本地验证”，不能写成官方成绩。
- 论文、图表和摘要只能使用已经实际运行并保存的结果；未知信息写明“待核验”，不得补造。

## 官方模拟器安全边界

- 只允许使用官方“演练测试”。任何界面出现“正式测试”时立即停止，不得启动、连接或提交。
- `--practice-ready` 只是人工确认记录，程序无法自动辨别演练和正式会话；运行前必须再次确认模拟器页面明确显示“演练”。
- 每次实验使用当前新演练会话对应的 `robot_id`，不得复用已结束会话的编号，也不要把账号、密码或 robot_id 写入 Git、论文或版本化配置。
- 比较两个策略时，每个策略都开一局新的演练；不要在同一会话中切换策略。
- 如果模拟器已有未完成会话，优先在界面点击“中止测试”，确认结束后再开始下一局。

## Mac / Parallels 共享目录

- Windows 只能读取 Downloads 共享目录下的副本；`/Users/xingyu/personal/数学建模` 不会直接出现在 Windows 中。
- 导出前在 Mac 仓库根目录执行：

  ```bash
  cd /Users/xingyu/personal/数学建模
  .venv/bin/python scripts/export_windows.py \
    --destination /Users/xingyu/Downloads/数学建模/B_repo_candidate_YYYYMMDD
  ```

- 导出目标必须不存在，脚本拒绝覆盖已有工作台；需要重复导出时使用新的目录名。
- Windows 默认路径为：

  ```text
  \\Mac\Home\Downloads\数学建模\B_repo_candidate_YYYYMMDD
  ```

  若共享名称不同，从 `\\Mac\Home\Downloads\数学建模` 浏览进入实际目录。
- Windows 端的演练输出也放在该共享工作台的 `.local/practice/` 中，Mac 可直接读取 `summary.json`、`provenance.json` 和 `actions.jsonl`。

## Windows 端初始化与运行

在导出工作台目录打开 PowerShell：

```powershell
py -3.12 -m pip install -r requirements\validated-py312.txt
py -3.12 -m pytest -q
py -3.12 run_practice.py --help
```

如果系统没有 `py`，将其替换为 `python`。设置当前演练的机器人编号后再运行：

```powershell
$env:CUMCM_ROBOT_ID = "当前演练对应的robot_id"
```

问题 3 和问题 4 的候选策略示例：

```powershell
py -3.12 run_practice.py --question 3 --strategy adaptive_q25 --practice-ready --output-dir .local\practice\q3_q25_YYYYMMDD-HHMM
py -3.12 run_practice.py --question 3 --strategy adaptive_q10_dynamic --practice-ready --output-dir .local\practice\q3_dynamic_YYYYMMDD-HHMM
py -3.12 run_practice.py --question 4 --strategy q4_joint --coverage triangular --practice-ready --output-dir .local\practice\q4_joint_YYYYMMDD-HHMM
```

`--output-dir` 必须是不存在的新目录。问题 3 使用自动七站流程；问题 4 默认主线是 `q4_joint` + `triangular`，历史 28 站构造用 `triangular_legacy`，方格基线用 `square`。

## 结果判读与报告

- 一局演练只有在 `completion_certificate: true` 且 `exit_ok: true` 时才算完整结束；否则按失败、超时或未确认处理。
- 重点检查 `virtual_time_s`、`mean_clear_time_s`、`cleared`、`measurements`、`distance_m` 和 `fallback_actions`，同时保留逐动作日志。
- q3 策略选型以 50 个共同源配置的本地配对实验为准，当前入口是 `adaptive_q10_dynamic`；官方 25 局策略组只用于协议、证书和日志完整性核验。q4 当前入口是 `q4_joint`，50 局本地配对平均 717.04 秒/源、46/50 局优于新基线。所有这些都是本地或官方演练证据，不能宣称正式平均时间或奖项水平。
- 任何官方演练结果都应记录会话标识、题号、策略、参数、时间戳和输出目录；不记录账号密码。

## 代码、验证与 Git

- 主要源码在 `src/cumcm_b/`，入口脚本在 `scripts/`，测试在 `tests/`，说明在 `docs/`，结果在 `results/`。
- 修改后至少运行：

  ```bash
  .venv/bin/python -m pytest -q
  .venv/bin/python -m ruff check src scripts tests
  ```

- 需要提交时只提交 B 题项目文件和验证证据；当前未跟踪的 `C题研究/` 属于另一项工作，除非用户明确要求，不得加入、删除或改写。
- GitHub 远端为 `git@github.com:Oblivionfun/shuxuejianmo.git`。推送前检查 `git status`、提交内容和是否包含敏感信息。

## 代理执行原则

- 优先做可复现、可审计的小实验，再扩大搜索范围；模型改进必须同时报告基线、改动、指标和验证边界。
- 不把“程序成功启动”“页面显示结果”或“本地仿真通过”写成“官方测试通过”。
- 论文中的公式、表格、图和结论必须与当前代码输出一致；产物发生实质变化后重新运行受影响的检查。
