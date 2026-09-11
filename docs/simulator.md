# Windows / Parallels 演练说明

[返回首页](../README.md) · [本地复现](reproduction.md)

官方程序和客户端都在 Windows 虚拟机内运行；Mac 的 `127.0.0.1` 不指向 Windows 回环。本机已验证的共享工作台是下载目录下的 `数学建模/B_workbench/`，此次整理没有覆盖它。仓库开发目录不在 Windows 共享范围内，需要导出独立工作台。

## 导出与自检

在仓库根目录执行：

```bash
python scripts/export_windows.py --destination ~/Downloads/数学建模/B_repo_candidate
```

导出目标必须不存在，脚本拒绝覆盖已有工作台。Windows 中通过 `\\Mac\Home\Downloads\数学建模\B_repo_candidate` 打开（共享名称以 Parallels 设置为准），然后：

```powershell
python -m pip install -r requirements/validated-py312.txt
python -m pytest -q
python run_practice.py --help
```

这些命令不调用模拟器。

## 仅演练连接

1. 在模拟器界面选择问题，确认明确显示**演练**并启动会话。
2. 使用当前演练对应的 `robot_id`，不要写入版本化文件。
3. 确认后才运行：

```powershell
$env:CUMCM_ROBOT_ID = "当前演练对应的 robot_id"
python run_practice.py --question 4 --coverage triangular --practice-ready
```

问题 3 使用 `--question 3`（自动七站）；q4 方格基线使用 `--coverage square`。`--practice-ready` 只是人工确认记录。四动作 API 不提供模式查询，客户端无法靠参数辨别演练和正式会话；当前授权范围为演练，禁止启动或连接正式测试。客户端没有启动新会话接口。

每局默认写入 `.local/practice/<时间>/` 的 `provenance.json`、`summary.json` 和 `actions.jsonl`，也可用 `--output-dir` 指定不存在的目录。退出码 0 只有在完成证书和 `/exit` 均成功时返回。超时仅重试相同请求 ID 与字节；状态无法确认时记录 `unresolved` 并停止后续动作。

七局历史演练的原始加密日志仅保留在本机；GitHub 中的汇总已匿名化。工程迁移本身不消耗任何演练或正式机会。
