# McPet 首发计划 · v0.1.0

用户任务：将面向用户的表达改得可爱自然，适量使用 DeepSeek 的梗；整理发行包并发布第一版。新用户默认 DeepSeek 娘；原麦麦角色显示为 ChatGPT 娘，麦麦套装仍是可切换皮肤。

单 Agent 完成，共享文案、入口和发布流程不拆并行轨。保留 Python、已有 MCP/Guard/台账和右键气泡交互。

1. 调整当前菜单、气泡、业务摘要、Agent 输出与技能口吻；明确确认、金额、未知提交语义不变。协议字段和旧 maimai 角色 ID 保留兼容，已保存选择继续生效。
2. 打包通用 Agent 源码包和 Windows 便携包；提供易读入门说明、技能和素材出处，不夹带凭证、本机配置、台账或测试日志。授权尚未澄清且无运行引用的 cetapet-whale 开发素材保留忽略的本机备份、从首发跟踪目录移出，避免 GitHub 自动源码快照包含它；Git 历史保留。
3. 运行适用回归、技能格式、编译、压缩包核对、解压后真实 stdio 与隔离数据的桌宠启动检查。保留首失败；历史 heartbeat/素材 RED 和未执行的真实账号操作独立说明。
4. 提交、推送、普通合并，创建 v0.1.0 GitHub release，上传核对后的包。用户已明确授权发行，无额外发布确认。

## 当前验证

- 25 个适用测试文件：438 passed（37.25s）。包含原 426 项、8 项技能安装/真实 stdio 测试和 4 项首发身份/回执/打包测试；完整命令见下方。
- `python -m compileall -q src scripts tests`、技能格式校验通过；技能校验使用 UTF-8 模式，PyYAML 仅开发工具需要。
- 首轮回归保留 `release-regression-first.log`：11 failed / 427 passed（200.39s）；主要是新文案与旧字面断言、订单确认不再展示技术 JSON，以及时间 fixture 的浮点/副实例测试同步问题。确认仍核对门店、餐品、券、金额、取餐方式及真实创建/付款含义。
- 二轮 `release-regression-second.log`：6 failed / 432 passed；固定旧时间导致 stale、剩余旧文案断言。最终 fixture 使用当前整秒 + 精确二进制小数，仍严格核对桶与时间；副实例 fixture 保持主实例到检查完成，原 10 秒上限和 heartbeat <150ms 均不变。三轮 438 passed，无跳过项。
- 首轮构建 `release-build-first.log`：缺少可选 MCP CLI 的依赖，改为收集实际 MCP client/server/shared；此前默认镜像未找到 PyInstaller，显式官方 PyPI 安装开发打包工具后继续。
- 首轮原生包安装 `release-native-first.log`：目录型资源的目标路径有误，缺少 OpenCode 模板；修正技能与模板打包路径并补“技能入口缺失时拒绝安装”。重新构建后必须做实际解压包验证，不能用源码测试代替。
- 原始日志都在忽略的 `.tmp-test-data/`，不进入 Git 或发布包。

适用命令：

```text
python -m pytest tests/test_first_release.py tests/test_agent_skill.py tests/test_deepseek_skins.py tests/test_agent_host.py tests/test_brain.py tests/test_guards.py tests/test_client.py tests/test_ledger.py tests/test_agentbridge.py tests/test_progress.py tests/test_metering.py tests/test_account_balances.py tests/test_main_startup.py tests/test_companion_panel.py tests/test_dual_pet_render.py tests/test_maimai_actions.py tests/test_schedule.py tests/test_config.py tests/test_pet_behavior.py tests/test_settings.py tests/test_app_actions.py tests/test_quota_panel.py tests/test_luckin.py tests/test_pet_menu.py tests/test_skill.py -q
python scripts/build_release.py --windows
```

历史联合桌面 heartbeat 与两项 DeepSeek 素材边界 RED 仍保留；首发回归不是完整测试全绿。真实账号领取/下单/支付、真实模型自动技能选择与全平台宿主验收未执行。
## 发行包实测

- 最后安装器变更后的接入复测：`tests/test_first_release.py tests/test_agent_skill.py tests/test_agent_host.py`，38 passed（49.27s）。
- `python scripts/build_release.py --windows` 三轮构建完成；最终 Agent 包 56,767,908 字节，Windows x64 包 119,131,002 字节。可复现构建工具为 PyInstaller 6.22.3，仅开发打包依赖。
- 两包压缩完整性、路径与文件范围核对通过；不包含真实 .env、宿主本机配置、台账、测试日志和未确认素材。压缩包检查曾在 Windows ZIP 尚未写完时过早运行，`release-archives-early.log` 保留 BadZipFile；等待构建进程完成后完整核对通过，未发布中间包。
- 实际解压后的 Agent 包：技能/引用复制、从另一个项目 stdio 启动、21 工具、DeepSeek 默认套装、无 Qt/独立模型导入和 EOF 退出通过（`release-archives-final.log`）。
- 实际解压后的 Windows 包：`McPet.exe --version`、通用与 OpenCode/Claude 安装、21 工具/7 资源、DeepSeek 默认、ChatGPT 显示名称、两套皮肤、无候选订单拒绝提交与 stdio EOF 通过（`release-native-extracted-final.log`）。
- Windows 可见桌宠：从解压包显式 `--desktop`，独立测试数据与关闭凭证/提醒；截图读回 DeepSeek 默认形象，实际右键 9 项功能菜单包含“躲一会儿”“回窝啦（退出）”。退出后测试 PID 消失、保存角色 deepseek/皮肤 default、stderr 为 0 字节。computer-use 输入动作本身为 unasserted，以上结论来自可见读回、偏好文件及进程/日志检查，不声称输入已获工具 verified 标记。
- 已安装本仓库最新两种宿主技能副本；生成配置不提交。已打开宿主需重新加载项目会话。未覆盖原用户保存的角色、皮肤、位置和提醒，也未重置原桌宠实例。

本地压缩包和构建缓存在忽略的 `dist/` / `build/`，原始测试、截图和本机素材备份仍在忽略目录；发行仅上传已核对的两个 ZIP。
GitHub 发布目标为 `v0.1.0`，发布正文在 [版本说明](releases/v0.1.0.md)。发布后的地址与包名通过 GitHub API 核对。
