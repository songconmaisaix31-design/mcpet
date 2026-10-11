# 麦麦小窝：Pixso、账号额度与双角色（2026-10-12）

业务依据：用户要求连接 Pixso MCP 重设计可爱小窝，按其 Orca 顶栏截图展示账号剩余额度，并使用 https://github.com/PC2005-cloud/dsh-pet 的 DeepSeek 娘，双角色可切换。沿用 Python/PySide6、原单实例和 Agent 会话辅助定位，无独立聊天框，保留麦当劳功能。基础 root 711c15ee7774de6fd6d5ad4427ad72364ee09d0f；原 A/B/C 和唯一集成轨继续，不新建 Worker。

## 范围与事实

- Pixso 官方远程 MCP：https://pixso.cn/mcp；主轨已执行 codex mcp add pixso --url https://pixso.cn/mcp，OAuth 等用户登录授权；尚未连接成功或创建设计。用户设计文件链接待提供。主轨维护设计与验收，C 等设计参数；可先完成数据、角色和 UI 接线，不宣称 Pixso 设计完成。
- 公共 Orca CLI `account list --json` 的 result.rateLimits 是现有顶栏数据来源，包含 codex/grok weekly、cursor monthly/buckets、claude unavailable；updatedAt/resetsAt 为 Unix 毫秒。2026-10-12 主轨只读采样 codex weekly usedPercent=16、grok=0、Cursor 两桶=0；这是账号缓存观测，不等于厂商即时结算。不得扫描/读取各账号 auth 文件或用户会话。
- 订阅额度展示已用百分比、剩余百分比、重置倒计时和最后更新；未知、失败、过期明确显示，禁止默认 0%、无依据合并窗口/桶，禁止把本机 token 换算成账号余额。截图参考紧凑图标+进度条+数字，不照搬黑色样式。
- DeepSeek 官方金额查询：GET https://api.deepseek.com/user/balance，DEEPSEEK_API_KEY；balance_infos 的 currency/total_balance/granted_balance/topped_up_balance 字符串以 Decimal 保留精度。无 key 显示未配置；金额不按任意 ¥20 上限伪造百分比。只查余额，不发模型请求。
- DeepSeek 娘取指定 dsh-pet 仓库现有透明动画，固定上游 SHA、保留来源与 LICENSE，验证 alpha/帧/锚点。只复用必要素材，不引入另一 Electron 应用、DSH 聊天或全部视频管线，不继续使用 CeTaPet 鲸鱼素材代替指定角色。

## 固定轨道与互斥写域

| 轨 | 原 worktree / branch / terminal | write_paths |
|---|---|---|
| A 角色与渲染 | mcpet-pet-20261011 / songconmaisaix31-design/mcpet-pet-20261011 / term_b6c07adf-6a39-472d-b48b-b8e6dede6b48 | src/pet/window.py、src/pet/spritesheet.py、src/pet/preferences.py、新 src/pet/characters.py、assets/dsh-deepseek/**、assets/CREDITS.md、tests/test_characters.py、tests/test_dual_pet_render.py、docs/companion/HANDOFF-A-DUAL-PET.md |
| B 账号数据 | mcpet-data-20261011 / songconmaisaix31-design/mcpet-data-20261011 / term_b879f5bb-8b59-41f1-85f7-0db4d16433c3 | 新 src/accounts/**、tests/test_account_balances.py、tests/test_account_monitor.py、docs/companion/HANDOFF-B-QUOTA.md |
| C 小窝应用 | mcpet-app-20261011 / songconmaisaix31-design/mcpet-app-20261011 / term_49f25b2c-dc4c-4552-8088-d633702a85d3 | src/main.py、src/config.py、src/pet/dialogs.py、src/pet/tray.py、tests/test_companion_panel.py、tests/test_settings.py、新 tests/test_quota_panel.py、README.md、docs/companion/HANDOFF-C-QUOTA-PANEL.md |
| 唯一集成 | 原 mcpet-companion-integration-20261011 / 原集成分支 / term_d599456d-aadb-4268-8d9c-f26901b8cf3f | 全轨完成后普通 merge；仅少量胶水、新 tests/test_dual_pet_quota_integration.py、docs/companion/HANDOFF-INTEGRATION-QUOTA.md；领域失败退原 Worker |

主轨仅写本计划、设计决定、状态、验收；Worker 不修改本计划或彼此写域。各轨先确认干净、fetch+FF 包含本计划的 root，再实施；完成 commit+push，给精确 tip/Handoff/首失败与验证/限制，然后停止。不得合并其他轨或合回 root。

## 共享契约（实现前有异议先 Handoff）

A：src.pet.characters 提供 CHARACTER_IDS=("maimai", "deepseek")、character_name(id)、load_character(id) -> SpriteSheet 兼容对象；maimai 复用 longniang。PetWindow.character_id 属性、set_character(id)->None，加载失败抛 SpriteLoadError 且保持旧角色。持久化 character_id 与位置/roaming/rest 同份偏好，保留旧键兼容；不创建第二 PetWindow/监控。切换缓存/帧/固定锚点正确，后台状态、拖拽优先级、TTL 与位置继续有效。A 在 Handoff 说明实际帧率和动画转换。C 用这些接口接角色 UI/托盘图标并按现选角色更新面板预览。

B：src.accounts 导出冻结 dataclass QuotaBucket(name:str, used_percent:float|None, resets_at:float|None)，MoneyBalance(currency:str,total:Decimal,granted:Decimal,topped_up:Decimal)，AccountStatus(provider:str,label:str,status:str,updated_at:float|None,buckets:tuple[QuotaBucket,...]=(),balances:tuple[MoneyBalance,...]=(),message:str="")，AccountSnapshot(accounts:tuple[AccountStatus,...],observed_at:float)。上述时间统一 Unix 秒；status 取 ok/unavailable/error/stale/unconfigured。OrcaAccountSource(command=None).fetch()->tuple[AccountStatus,...]；DeepSeekBalanceSource(api_key="").fetch()->AccountStatus。Qt AccountMonitor(parent=None, *, orca_source=None, deepseek_source=None, interval=300.0) 提供 snapshot_ready(object)、failed(str) 信号和 start/refresh/stop；start 不阻塞 GUI、refresh 合并请求、stop 立即返回且后台有限超时并回收，失败保留上一份成功值并标 stale，不暴露原始异常凭证。C 构造 DeepSeekBalanceSource(config.deepseek_api_key())。不得修改 AgentMonitor 四信号四方法或使用 UsageMeter。Orca 子进程 finite timeout/no shell、正确 Windows UTF-8 解码并捕获解析错误，只提取白名单 rateLimits，不保存账号/密钥/整包 metadata。金额合法非负，未知/NaN/缺少字段不变 0。

C：唯一面板可爱温暖奶油色+圆角卡片，兼容 DPR1.5 和小屏滚动；额度在首页明显位置，订阅窗口/桶各自展示，Cursor Models/Other Models 不相加；本机历史用量保留在会话页且有明确标签。首页双角色选择器与预览；设置 masked DeepSeek key，留空保留、明确清除、持久化 allowlist/redact；刷新按钮走 AccountMonitor，不触发其他读写/网络模型。配置保存后更换余额源时停止旧源后再刷新，不能重复 worker。四入口最小化恢复、麦当劳确认门槛均保持。

## 验收与边界

2026-10-12 C 接线决策：B 的新 AccountMonitor 增补公共 reconfigure(*, orca_source=None, deepseek_source=None)，None 表示保留；正在执行的有界只读查询可完成，但更换源后旧源结果不作为新凭据结果发布，pending refresh 合并，始终同一个监控对象/至多一个活动查询。reconfigure 不阻塞 GUI，不重新构造另一个 monitor；C 保存 key 后调用它再 refresh，UI 显示刷新中直到新源快照。可增加 stopped 信号用于验证回收，退出仍不在 GUI wait/join。旧 tests/test_app_actions.py、tests/test_main_startup.py、tests/test_companion_integration.py 的默认账号源离线注入由唯一集成 Worker 接线，保留所有旧断言与门槛；C 仅写新自域测试并禁网络。

正确 WorkBuddy Python；隔离 MCPET_DATA_DIR/TEMP 与受控 generic logs。适用测试+完整 pytest+compileall src tests+diff --check；保留每轮首 RED，修复后独立 GREEN。新组合测试真实 Qt、切两角色、重启持久化/拖拽/TTL、额度未知/失败/stale/Cursor分桶/Decimal、刷新合并、shutdown/进程回收；mock 网络只证明契约。原联合 heartbeat<150ms/stop<50ms、单 usage writer、四入口恢复不可放宽。DPR1.5 原生截图首页/设置与双角色；动画透明、无空白帧与锚点抖动探针。

主轨最终普通 FF、审图、只读实测 Orca cache、DeepSeek 有已配置 key 时余额 GET（不输出 secret，没 key 明示未实测），优雅重启现用户实例复验。严禁 Worker 操作用户 GUI49784/launcher38676/monitor23860/48728、读取 .env/凭证/既有会话、17GB日志根或 ledger、真实模型/MCP账号写操作。素材公开仓库下载允许；不安装/运行第三方 DSH 插件。Pixso 连接与设计输出需实际工具证据，未完成则单列限制，不能用本地 Qt 图冒充 Pixso。
