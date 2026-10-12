# 开发与验证

先读 [README](README.md)、[项目 Agent 约定](AGENTS.md) 与本次任务相关计划。
当前默认运行在原 Agent；目录与兼容入口见 [仓库结构](docs/REPOSITORY.md)。

## 环境

Python 3.10+，当前已验证的项目解释器为 Python 3.13.12。
只运行 Agent 服务安装 `requirements-agent.txt`；修改或运行现有测试使用完整依赖：

```powershell
python -m pip install -r requirements.txt
```

素材离线转换另需 Pillow、numpy、opencv-python 和 FFmpeg，按各素材 SOURCE 说明安装；
这些不是 Agent 服务运行依赖。

配置示例见 [.env.example](.env.example)。测试不需要真实模型 Key 或麦当劳 Token。
`tests/conftest.py` 默认隔离本机数据目录并使用 Qt offscreen；现有测试共享 Qt fixture，
因此即使只运行宿主测试，也需要完整测试依赖。

## 适用验证

Agent 接入修改的协议与业务回归：

```powershell
python -m pytest tests/test_agent_host.py tests/test_brain.py tests/test_guards.py tests/test_client.py tests/test_ledger.py tests/test_agentbridge.py tests/test_progress.py tests/test_metering.py tests/test_account_balances.py tests/test_main_startup.py tests/test_companion_panel.py tests/test_dual_pet_render.py tests/test_maimai_actions.py tests/test_schedule.py tests/test_config.py -q
python -m compileall -q src scripts tests
git diff --check
```

完整测试可运行 `python -m pytest -q`，但历史桌面/原生前台性能项存在尚未解决的 RED，
见 [接入验证](docs/AGENT-HOST-VALIDATION.md) 与 [桌面 Handoff](docs/companion/README.md)。
以上适用回归通过不等于完整测试或旧桌面动态验收。

宿主本机检查：安装接入后使用 `opencode mcp list` / `claude mcp get mcpet`。
前者连接成功和后者发现配置分别记录；Claude 原生首次信任由用户确认。
真实 stdio、离线业务 fixture、真实宿主 UI、外部账号写入和人工验收应独立标注。
不能根据 idle/Stop 推断任务完成，也不能把用量台账当厂商余额。

## 修改和提交

小任务单 Agent；并行仅用于可按互斥文件路径拆开的任务，并遵守用户的 Orca 轨道协议。
保留现有目录与技术栈，跨轨修改交 Handoff。按阶段 commit，最终分支 push，普通合并，
不 force push 或覆盖公共历史。不要删除队友分支、worktree 或无法解释的文件。

本机生成的宿主路径配置、真实凭证和个人运行数据不入库。只整理能解释来源的缓存，
保留首失败与待验证记录。素材保留 SOURCE、许可证和 [来源说明](assets/CREDITS.md)。
