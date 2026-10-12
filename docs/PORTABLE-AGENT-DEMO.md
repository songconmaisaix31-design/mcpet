# 通用宿主接入与动作演示（2026-10-12）

事实源：用户要求“不绑定宿主 Agent，演示这两段视频”。基线为 main / aafcd712。
本任务由单 Agent 在 codex/portable-agent-demo-20261012 完成，保持既有 Python/MCP/素材目录。

1. 默认接入输出通用 stdio 服务定义，不写指定品牌的配置；原生安装器作为显式可选适配保留。
2. 使用无品牌 MCP 客户端实际连接，验证工具及两份动画资源；不依赖任何宿主插件。
3. 在当前工作台打开一次性本地演示，展示用户原 MP4 与已导入的透明 GIF；不增加产品交互入口。
4. 本地预览仅监听回环地址、只提供指定素材，不扫描其他文件或上传视频。
5. 运行适用回归、编译和 diff 检查；提交、push，并普通合并到 main。

假设：宿主须支持 MCP stdio 才能直接接入；图像呈现能力与工具连接能力分开验证。
原生 hooks 是可选增强；无 hooks 的宿主仍能使用全部工具和资源，通过工具主动查询提醒/状态。
本轮不改写旧 GUI/foreground/heartbeat RED，不执行真实订单或模型请求。

## 使用

在 McPet 仓库运行 `python -m src.agent_install`，将输出的 `server.command` / `server.args`
填入当前宿主的 MCP stdio 设置。外层容器按宿主要求配置；服务端不识别或限定宿主品牌。
OpenCode/Claude Code 安装器仍可通过显式 `--client` 使用。

预览两段用户提供的原视频和对应透明动画：

```powershell
python scripts/demo_actions.py --frying-video "你的炸薯条视频.mp4" --outfit-video "你的换装视频.mp4"
```

打开输出的 `http://127.0.0.1:8769/`，点击“播放 / 重播两段”。原视频默认静音，可在播放器中打开声音；
炸薯条循环，换装一次。GIF 分别为 10.16 秒，原视频约 10.08 秒。
Ctrl+C 停止预览。此脚本仅提供 5 条指定页面/素材路由，不提供仓库目录浏览，不上传素材。
需要时显式运行；日常 MCP 服务不会启动预览，也不会新增业务窗口。

## 本轮验证

- 默认导出不读取或改变已有品牌配置：含无效 `.mcp.json` / JSONC 的隔离目录保持原样。
  真实无品牌 SDK 客户端使用导出的绝对启动器，从另一 cwd initialize、取得 17 工具，
  选择两个动作并读取两份 GIF，均通过；不依赖原生 hooks。
- Orca 工作台本地浏览器实际加载两段用户原视频，均为 720×720、10.08 秒。
  炸薯条持续播放循环；换装到 10.08 秒结束。重播后的两次采样相隔 2.2 秒：
  炸薯条 0.715 → 2.938 秒、3315 → 3368 解码帧；换装 0.681 → 2.901 秒、264 → 317 帧。
  两段画面像素摘要均变化。透明 GIF 加载成功、尺寸均为 192×192，截图已目视检查。
  播放证据 `.tmp-test-data/portable-agent-demo-playback-retry.json`，截图 `portable-agent-demo.png`。
- 预览 HTTP 的 5 条指定路由均返回正确素材/MIME；4 条其他文件、目录和穿越路径均 404。
  结果 `.tmp-test-data/portable-agent-demo-http.json`。原视频未复制入仓库或上传。
- 首次 `snapshot` 与一次原样重试均报 `browser_owner_unavailable`；未关闭其他进程或更改 Orca。
  `eval`、截图及实际播放通路成功。首个动态采样表达式含不支持的顶层 await，返回
  `browser_eval_error`；改为异步表达式后采样成功，原日志 `portable-agent-demo-playback.json` 保留。
- 首轮适用回归 **315 passed / 1 failed**（138.36 秒）：旧桌面重复启动测试未得到 secondary 结果。
  当前代码未修改该测试或桌面锁/计时器，未确认失败根因；首日志 `portable-agent-demo-regression.log` 保留。
  同一项原样重测 **1 passed / 4.60 秒**；完整适用命令原样重跑 **316 passed / 42.99 秒**，
  日志分别为 `portable-agent-demo-duplicate-retest.log` / `portable-agent-demo-regression-retest.log`。
  该重跑不覆盖首失败，也不代表旧桌面性能问题已解决。

适用回归命令（与贡献指南的 15 个文件一致）：

```powershell
python -m pytest tests/test_agent_host.py tests/test_brain.py tests/test_guards.py tests/test_client.py tests/test_ledger.py tests/test_agentbridge.py tests/test_progress.py tests/test_metering.py tests/test_account_balances.py tests/test_main_startup.py tests/test_companion_panel.py tests/test_dual_pet_render.py tests/test_maimai_actions.py tests/test_schedule.py tests/test_config.py -q
python -m compileall -q src scripts tests
git diff --check
```

编译与 diff 检查通过；41 份 Markdown 的 83 个本地链接无缺失。
业务验证为离线 fixture，stdio 与浏览器素材播放是真实本机执行；未测试真实订单或模型调用。
此次是工作台浏览器演示，不等于任意宿主终端可内嵌动画；可选原生 hooks 仍只有已有两个适配。
无 hooks 不影响工具/资源调用，自动状态推送需要对应宿主提供事件并实现适配。
