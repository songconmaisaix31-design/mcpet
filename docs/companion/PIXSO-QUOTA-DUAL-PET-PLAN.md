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

## 2026-10-12 主轨审阅追加

- Pixso 后续实际完成 OAuth、24 工具发现及专用新文件首页 frame 3:1 的生成/截图；早期未连接记录保留。实际设计与链接在 PIXSO-DESIGN-BRIEF.md、PIXSO-HOME-DESIGN.png；设计示意不能成为产品余额。check_layout 返回 null，没有自动布局通过结论。当前 Orca 账号 home 已添加 Pixso 配置，但此 home 的 OAuth 因代理访问超时尚未验证；默认 Codex home 的真实授权/设计已成功。
- B 解析审阅返修：Codex/Grok/Claude 仅接受已知 session/weekly 窗口，有 session 则独立显示，不提供时不造数；Claude 有合法窗口时不得一律 unavailable。窗口不相加，缺失/非法保留未知，Cursor 契约不变。返修只由原 B 写域实现并重新验证。
- A 本地最终 tip 8b7da5c9d396a0e14b77f4e2b7ad5c844c0c4a1e；远端 push/ls-remote 尚未确认，不作为已发布/集成。C native-v1 额度卡压缩是视觉 RED，v2 修复并有尺寸/小屏测试；最终紧凑布局与双角色原生图仍待审阅。原 C Codex 因内存分配失败退出，工作区改动保留，在原终端 resume 同一 cwd 会话，不新建 Worker。
- 系统代理端口可连接但 Pixso/GitHub 超时，主轨未修改全局代理、未复制 OAuth 凭据、未重启其他进程。各轨仍可本地验证；发布需远端证据，现用户旧 GUI 保持运行，最终集成/优雅重启尚未执行。

后续恢复记录：用户继续指令后网络已恢复，root ee1b583 普通 push/ls-remote 成功。Orca runtime 重启后旧句柄失效，按元数据查到准确原会话 ID 恢复 A/B/C；`resume --last` 曾选中 root，已在目录选择页取消，未启动复制会话任务。首次直接恢复采用默认执行权限导致 helper setup refresh 错误，按当前已授权 danger-full-access/approval never 恢复后各轨 exec 正常；此为环境失败，不计测试 RED。原 A/B 的终端已不存在，因此仅补回原会话的终端，不创建新 Worker/worktree/branch。

当前 root terminal 为 term_2a23bbea-71c5-4f99-b15f-77e5b8ca591b；A term_7ec38c47-7c51-4aa8-b2f2-dac9374fb8a8、B term_465fe177-ce16-48ab-98a8-7388246699ff、C term_f6e5acc2-570f-4908-a1e7-0c85933a05e1。原会话 A=01a12b90-062a-7f70-b3a5-595326746751、B=01a12b90-ae7e-7610-a359-446106d5f5d9、C=01a12b90-c2c2-7cf3-ade5-5dd6a0f77166、集成=01a12baa-554e-7d32-8835-e1865e39d601。

A 已普通 push，root 独立 ls-remote exit0 确认 8b7da5c9d396a0e14b77f4e2b7ad5c844c0c4a1e，A 通知同 SHA/干净并停止，未新增代码或重复完整测试。当前 Orca 账号 home 的 Pixso OAuth 后续浏览器确认成功，实际 app-server mcpServerStatus/list: authStatus=oAuth、toolsError=null、tools_count=24；50 秒父命令等待超时与浏览器 wait url 不支持已单列，最终以回调 Authentication complete 和实际 MCP 状态为准。未导出/复制密钥。仍待 B/C 收尾、原唯一集成和主轨最终运行验收；只读进程核对已无先前用户 GUI49784/launcher38676/监控23860/48728，也未找到 -m src.main 常驻实例，最终启动前需再次核对。

## 原生审图与串行复验追加

当前账号 Pixso 后续真实 fetch_context 成功读取本次新文件（未选中节点、无 schema/map 导出）；无模型 turn，无额外设计修改。

C 新紧凑布局 cold quit 首 RED 149.35ms，profile 108.84ms（panel.hide 65.71ms、退出气泡 41.74ms），随后 85ms/71ms 诊断也保留；不是账号 stop 的阻塞结论。C 改为 quit 同步拒绝新动作/stop现监控，SerialTasks 安全结束信号再统一关闭原窗口/面板，原50ms gate保持；需补实际活动请求有限结束/窗口关闭/QThread与进程回收，不能只测提前返回。首借 A native 20s monitor timeout、network_calls0、worker_stoppedtrue保留，诊断补错误信息且未延长预算。

root 实际 view_image 审 native-compact 三份主页，发现 Codex 已用16.25%与 Cursor 两桶文字被窄 summary 裁切，退回原 C；这一版是视觉 RED，29适用 PASS 不等于可验收。v4 限制 bar 占宽并让 summary/reset 获得完整空间，未继续缩字体；加入700/560真实 heightForWidth 可读性断言。root 已审六张 v4 图，Codex16.25%、Cursor20%/90%、四 provider、金额/币种、双角色真实预览均清楚，其他三页视觉通过。图在 C:/Users/DW/AppData/Local/Temp/mcpet-c-quota-final-1791751045265/native-compact-v4/；DPR1.5、network_calls0、errors[]、worker_stoppedtrue；A8b7da5c只读overlay，无merge/复制。仍是受控夹具，不代表真实账户/任务完成。C30适用 PASS/32.18s、stop4.3066ms后明确测试空闲，暂做静态/Handoff。

B 窗口返修 f77cbbee6fc7720b742f56c9fc5fa578118ece9d，含实际 session:null；62解析 GREEN。首完整5failed/396passed/211.43s：三类whole-exit时限、旧联合heartbeat1135ms、旧duplicate未命中，保留且不改跨域；CPU76%只为样本，原因未确定。C明确空闲后B串行账号82passed/32.33s，无门槛/Monitor修改。主轨要求再一轮原计划完整pytest、compile/diff、push/remote核对，之后交回C最终完整与联合测试；测试结果不得混成全套GREEN。仅用既有消息协调时段，无并行性能探针。B诊断曾误用showlocals带出继承环境，B已清理其诊断行，不再使用或转发，root不继续读取该类原始环境诊断。

唯一集成 Worker 待三轨精确远端最终 tip/停止后恢复原会话。其可接线旧 tests/test_app_actions.py、tests/test_main_startup.py、tests/test_companion_integration.py 的 AccountMonitor stub，以防默认真实余额/Orca访问；保留旧断言与heartbeat150ms/stop50ms/四入口/单writer。新 tests/test_dual_pet_quota_integration.py 应真实 Qt+AgentMonitor+AccountMonitor、顶层可pickle受控源，验三个read worker的有限回收以及一个usage writer；各域问题退原 Worker。root按最终联合结果再FF/审原生图/真实只读额度/单实例启动，不以当前分轨结果声明组合完成。

## B 最终交接与 C 测试时段

B 最终远端 tip fa96c57801d705f21b400f6f5271745d9914d421，解析实现 f77cbbee6fc7720b742f56c9fc5fa578118ece9d；root 独立 ls-remote exit0 确认，B 通知工作区干净、停止且无测试探针。串行账号适用82 passed/32.33s；最终完整1 failed/400 passed/110.65s，仅旧联合 heartbeat417.81ms>150，stop42.8088ms<50、首panel_open332.09ms、errors=[]；原因未认定，不能称全套GREEN。账号全部Windows退出与旧duplicate本轮通过；compileall/diff检查通过。首完整5 failed/396 passed/211.43s及其他首次RED保留于HANDOFF-B-QUOTA.md。

root 已将独占测试时段交回原 C：活动任务有限退出、原联合、最终完整、compile/diff及精确push/remote交接。v4六图已视觉通过，C无需另改装饰；旧联合若失败只Handoff，保留门槛与领域界限。等待C最终远端tip和停止后，再恢复原唯一集成Worker，完成真实双角色+账号监控组合、离线测试接线与最终性能验证。

## C 最终交接与统一集成派发

C 最终远端 tip 1b2b08ed0dcd5790a11a14d70bc1fbf8d1d83488，代码 cde12f86d330039b4d3e89e4313daabb251c9e46（功能 eb6858e7c5c98c541fed62224f48ed8c6d1a322a），root独立ls-remote确认；C已停止/干净/无探针。适用66 passed/55.81s；独立真实原生活动退出1 passed/11.67s，stop3.7113ms、两spawn回收/锁删除/位置与休息闲逛重启恢复通过。最终完整1 failed/340 passed/103.99s，仅旧联合heartbeat554.15ms>150，首panel467.37ms、stop5.1700ms；不能称全套GREEN。首次联合439.24/345.08/stop9.5934、错root诊断和cached EOF diff RED均保留；后续普通空行提交、compile及含新文件全分支diff通过。

冷show分段显示数据约1–5ms、构造28–74ms/layout12–14ms，首次show主导；字体合并、全局过滤、owner、样式、报告方块字符、accessibility对照未消除RED，没有确定根因。全部仅TEMP诊断，未预热或扩大业务。组合后如仍复现交回原C，不能调大门槛、等待TTL或移动心跳计时规避。v4六图视觉通过依然只是受控fixture/只读A overlay。

三轨最终tip均已远端核对、停止，现恢复原唯一集成会话01a12baa-554e-7d32-8835-e1865e39d601（原worktree/branch，当前干净7a828d0e）。先FF本主轨计划，再普通merge A8b7da5c、Bfa96c578、C1b2b08ed；接旧测试账号离线stub并新增真实Qt/AgentMonitor/AccountMonitor组合测试，保留全部原断言/预算。先独立联合验证，若领域RED明确Handoff原Owner；胶水外不得修改领域代码。root最终FF/真实账号缓存读取/启动仍未执行。

## 集成检查点、C 消重与 A 渲染返修

唯一集成普通merge A/B/C SHA分别47c6ebc612f2163d3f8bcaf15044d31fdf514839、4b0c996b5a36ba8177a4bd79321ac928d81329b4、8161099c0938f9c3c420580c82da47ad7a11a1d5；已发布检查点bf5ff01ca8de33ad417eb7fd1cacd64030177d5b，root独立远端核对。旧联合首RED heartbeat545.25ms/首panel458.47ms/stop3.3559ms，后置PID/锁/重启NOT_RUN；新组合更正协议后1 passed/1 failed，真实两monitor/三reader回收/单writer/四入口/双角色/换源/Decimal契约通过，heartbeat2739.76ms仍RED。旧接线22通过，完整及六图留返修后；Handoff保存所有首次失败及测量界限。

原C从检查点FF后发布d037c5cf6b384d4930dbadef97b0240881978b73（代码876ae0c8632ded4b172dfac35be5184ad1295bda），root独立远端核对。71适用通过、实际30次action_quota3.7535ms、icon0.15–0.48ms，同结构新快照原位更新、错误刷新保留stale/换key清旧卡片；compile/diff通过。C保持同步激活语义，不采用预热或延后计时；空窗口show336.71ms、首次激活多种对照仍超门槛，没有确定系统根因。旧联合383.09ms/首294.02ms、新组合2290.13ms；最后诊断role_frames_advanced=false、heartbeat3261.51ms/首765.25ms；C native show559.27ms/新结构重建425.16ms仍未解决，完整NOT_RUN，v4视觉复用。C已停止且三受控PID无残留。

原A从C已发布basis d037c5c干净FF接续，当前独占测试时段，root/C/集成均不跑动态探针。分段确认整idle解码268ms、必要working解码308ms、麦麦透明校验325ms，而单帧缩放最大3.34ms；PNG小分页及透明校验优化正在原A域实施，保持同像素/固定cell/节奏/同步失败事务/有界缓存。旧/新联合首RED及role帧推进失败保留，未宣称通过。返回麦麦原WebP解码仍有305ms样本。

write_paths最小增补：仅原A可新增 assets/longniang/spritesheet-runtime.png，作为现有spritesheet.webp的同像素无损运行缓存；源WebP、pet.json、sprite-rows.json及其他轨资产保持，许可/转换依据写原A已拥有的assets/CREDITS.md和HANDOFF。是否使用必须实测像素/alpha一致、冷解码和内存，并通过原A的characters.py接线，不让A改C/main。此项是减少已测得的必要源解码成本，不是预热或新目录/角色框架。原A仍不能改main/dialogs/accounts/旧或新集成测试。最终唯一集成除普通merge C/A返修tip外，还需普通merge包含本追加的root文档tip，保证主轨最后可FF，领域RED继续退原Owner。

## A 发布返修、合并审图与 C 下一轮界限

原A返修最终远端7d06474e4cbbf86d0517cc94f2b8c088c08532e5，root独立ls-remote确认，原A干净且已交回测试时段。代码538e25e/476066c/ca3cf5f：94 PNG分页与独立预览、同节奏活动timer/deadline保留、alpha字节校验、麦麦同像素stored PNG。71适用通过/21.01s，原10s bench和双角色native通过；发布新组合完整契约与帧推进通过，但heartbeat829.28ms/首391.90ms仍RED，旧483.55ms/首397.53ms仍RED，原A本轮完整NOT_RUN。正常点击stored PNG解码118.466ms/切换164.059ms、同版WebP对照288.028ms/330.345ms；较大磁盘体积换解码CPU，不能称所有角色切换已低于150ms。不存在先前候选_reload_frames/resizeEvent重载；记录该候选未成立，不作为修复证据。

唯一集成已普通合并C d037、A 7d06474和root cfde794，merge分别c8d3bb97777939d0768554125974445c4fe72d01、ed834e2d52fa9da8e938b06615a78bdbac4f1f2e、e1824f729ee4f0fc6bcb31ee3db22cbba95821df，无代码/协议/断言修改。本轮独立旧联合首RED heartbeat795.87ms/首703.67ms/stop8.2874ms，heartbeat后整体退出/PID/锁/重启NOT_RUN；新组合完整行为与退出契约通过，heartbeat2526.44ms仍RED。按用户明确要求执行唯一一次完整pytest：450 passed、2 failed/182.31s，两个失败均为原heartbeat门槛，旧545.93ms、新1038.21ms。不得以450通过宣称全套或产品验收通过。

root实际审阅本轮native-six/screenshots六张1050×1080原生图，DeepSeek首页另按original完整复看：双角色、Codex session/weekly、Cursor monthly与两桶完整百分比、Grok有效0/Claude UNKNOWN、独立CNY Decimal及四页视觉通过。证据在C:/Users/DW/AppData/Local/Temp/mcpet-integration-quota-review-44589ca99b8b4bf8905beb5585dd82e5；实际合并的真实监控/受控源、无网络，账号值明确夹具，非live。性能RED保留，root尚未FF、真实额度采样或常驻启动。集成完成compile/diff、有限回收、push/精确remote后发布review basis并交空闲，不重复同版全套挑GREEN。

原C已仅静态提出下一轮方案，未修改或启动探针：首次实际快照才创建provider行；换key同步清所有旧文本、金额、时间、tooltip/accessibility、进度条和倒计时引用，暂存有限的已清空隐藏行；新快照仅增删真实变化provider及桶/金额行并完整更新字段，真实空快照清除缺席行，保持UNKNOWN/stale/Decimal与560/700可读性。不得预建示例卡、保留旧key可见值或累积历史对象。只有集成发布精确basis且明确slot idle后，root再给原C干净FF及本域实现/验证授权；目前动态测试仍由唯一集成独占。

首次激活尚无确定根因。C后续可在自有TEMP/自有HWND补同段wall/thread CPU和消息嵌套关联，以区分实际计算和等待；不能把空窗口336ms推成系统根因、禁用accessibility/改全局设置、操作其他窗口/进程，或通过延后激活/移动心跳/预热/放宽150与50ms规避。仍保持四入口真实前台恢复语义，领域修复归原C，原A/B与集成不越域。

## C 卡片生命周期发布与限定诊断

唯一集成已发布review basis 7ffeebd03179a2796cb88fb73e52929d22bbca6c，包含root 7fec18b930559804b01ad785d5dc4bca44ec3f09（merge fa779ff604721ffaef068f5699765031ac4c4f6b），远端与工作树核对一致，全部动态探针结束。实际合并六图已审，完整450通过/2失败仍非最终交付。

原C从该basis发布36001485cb03b940c4d3f2eeee5b40915943865f（业务0c4c5f80bd291a3faeb16b8ccb61e545601c7c5a），root独立ls-remote确认。旧隐藏标签36降至0、实际provider复用0至5、新快照205.2712降至86.831ms是成对样本；全量清旧文本/可访问内容/进度条/倒计时、真实结构增减及空快照释放已有自域回归。最终C自域41通过/1失败67.69s，唯一新增Windows前台断言仍失败；旧联合heartbeat646.03ms/首542.64ms/stop6.5979ms，新组合1通过/1失败23.68s、heartbeat2934.91ms/首621.34ms/stop8.2941ms，真实行为及有限回收通过，原门槛仍RED。本轮完整仓库及更新六图NOT_RUN，所有首失败和探针修正保留在HANDOFF-C-QUOTA-PANEL.md及mcpet-c-lifecycle-1791758072944。

新增前台测试使用程序信号和QTest直接输入，当前Qt active、本GUI线程焦点及Qt输入为true，但特定panel HWND与原生前台不等。微软SetForegroundWindow和Qt activateWindow文档均有后台激活限制；未证明此探针具有真实用户last-input/前台权限，不能凭Qt输入推成人工键盘验收，也不能凭该差异直接认定产品缺陷。保持新增首RED与全部原断言；不采用删测试、skip、替代断言或全局抢焦点刷绿。

root重新把独占时段交原C，仅授权两项TEMP诊断：一次原四入口观察，分类前台句柄为本进程/其他/null；只有归属本进程才比自有HWND及root/owner关联，不记录外部PID/窗口内容。另做原版与仅保留未访问页tab shell的冷新进程单对照，保持真实home/数据/角色/尺寸/样式/DPR、正常show/activate、连续心跳与可访问性，观察未访问sessions/mcd/settings控件是否造成首home显示成本。该控制仅TEMP，不预热、不延后当前页或激活、不修改业务/原协议；没有改善即停止候选。有明确改善后root再决定本域最小按需页面实施，每页首次实际访问仍须计同步耗时与连续心跳。当前原A/B/唯一集成继续静态等待，root不跑动态探针、不FF或启动常驻实例。
