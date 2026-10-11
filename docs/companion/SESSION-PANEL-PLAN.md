# 会话辅助桌宠与统一小窝面板（2026-10-12）

最新用户要求优先于上一轮聊天规划：项目依托 Agent 会话，不设计独立聊天框；设置用可爱 UI 放在一个框里。保留现有 Python/PySide6、原角色资产、自动 AgentMonitor、麦当劳功能、安全退出及写操作确认。移除应用独立模型聊天/聊天记忆入口；历史 chat.json 和旧模块不无故删除，不自动迁移/发送旧对话。CLI 能力不扩大或无故删除。

官方依据：[OpenAI Pets](https://learn.chatgpt.com/docs/pets)，已读取本日正文。它将宠物定位为工作活动伴侣，状态有 Running/Needs input/Ready/Blocked，并允许回到主应用会话。官方当前也有 Quick Chat；本项目按用户明确要求不采用独立聊天。此处只借鉴会话活动和控制面板，不宣称已经接入官方内部 API 或能向既有 Agent 会话注入请求。

## 单一修改轨

继续原 C Worker / Worktree / Branch，不新建并行轨。基于本计划提交后的主分支普通快进，固定写域：`src/main.py`、`src/config.py`、`src/pet/dialogs.py`、`src/pet/tray.py`、原 C 测试以及 `tests/test_companion_integration.py`、新增 `tests/test_companion_panel.py`、`README.md`、`MCP_INTEGRATION.md`、`docs/AGENT_BRIDGE.md`、`docs/companion/HANDOFF-C-PANEL.md`。不改 A 动画/手势、B monitor/业务，不读取凭证、用户聊天或进行网络/账号写操作。主 Agent 仅维护本计划和最终验收。C 完成后原唯一集成 Agent 普通合并及组合验证，领域问题仍交 C。

## 行为和可视要求

- 桌宠保留单击摸摸、拖拽、闲逛/休息；现有双击信号连接统一小窝面板。托盘/右键主入口同一个面板；去除“问麦麦/聊天/发送/偏好记忆”入口，App 不实例化 ChatDialog/ChatStore、不调用 StepFun/run_skill 形成新会话。
- 一个可重用、非模态 Qt 面板：“麦麦小窝”。原角色预览、奶油底色、暖橙按钮、淡紫卡片、圆角、清晰的中文标签，布局紧凑并兼容本机 DPR1.5 和工作区。不新增素材/引擎，不用装饰动画增加 CPU 扫描或 UI 负担。
- 面板内页签/卡片整合陪伴控制、会话活动与本机用量、麦当劳操作、设置。进度/用量/设置不再各开独立详情框；重复打开、关闭重开只复用一个实例，监视信号实时更新同面板。活动列表保留真实 source/label/state/context、未知/过时/错误语义，不显示虚假任务百分比或厂商余额，不加会话输入框，不假装可以打开/控制原会话。
- 设置保留 MCP 凭证掩码/不回填/留空保留/显式清除，城市及显式 Agent roots；高级目录可折叠。独立 StepFun 聊天凭证从主面板去掉，既有本机配置不删除。保存/取消语义清楚，root 改动提示重启，旧 monitor 期间不创建第二个写入者。
- 麦当劳查询和饭点提醒继续只读；下单/撤单/领券确认、真实选餐品份数、付款安全流程保留必要业务确认框，不能为“一个框”删掉账号写确认。无额外自动联网或模型请求。

## 验收与交付

收尾补遗：C 检查发现 A 的 `src/pet/window.py` 触摸气泡仍写“双击我可以聊天”。恢复原 A Worker/Worktree/Branch，仅授权该文件的这句用户文案改为打开小窝；不改手势/状态/动画，不跨 C 写域。A 快进本计划提交，核对现有触摸回归，commit+push+交接并停止。原唯一集成 Worker 普通合并 C 和此 A 文案 tip 后组合验证。

更新旧聊天接线测试为“触摸 + 双击统一面板/关闭重开 + 拖拽/休息 + 实际 monitor”组合回归；单窗口复用、标签入口、真实信号更新、设置保存与取消/掩码、缺凭证不影响会话显示、零聊天/模型请求须有必要测试。用正确 WorkBuddy Python 运行完整 pytest、compileall、diff check 和 Windows Qt 组合探针。用隔离受控日志/测试凭证截图可爱面板，不读取真实用户数据。首失败保留。C commit+push+handoff+停止，原集成 Worker 合并并 push 后主分支 FF。主 Agent检查截图，并优雅关闭本轮之前启动的已知旧桌宠、启动新版供用户操作；不杀其他项目进程，不重跑17GB冷回填作为 UI 改动验收。
