# Agent 技能层

任务：将现有 McPet 能力做成可在原 Agent 使用的技能，保持宿主中立，复用 MCP、Guard、台账和既有桌宠。单 Agent 完成，不引入新模型或大界面。

## 入口与安装

仓库内 `.agents/skills/mcpet/SKILL.md` 是唯一技能源，餐饮流程在相对引用 `references/orders.md`。支持该项目技能目录的宿主可直接发现；具体技能刷新方式沿用宿主。
标准 MCP 客户端无需支持技能格式也能使用 21 个工具及服务端 prompt；支持技能的宿主可用技能改善路由与多步操作。

```powershell
python -m pip install -r requirements-agent.txt
python -m src.agent_install
# 需要复制技能时：相对目录以 --project 为准，可传宿主自己的绝对 skills 目录
python -m src.agent_install --project "目标项目" --skill-dir .agents/skills
# 可选品牌适配，同时安装 MCP、原生事件与同一份技能
python -m src.agent_install --project "目标项目" --client opencode
python -m src.agent_install --project "目标项目" --client claude
```

通用命令不读写品牌配置；指定 `--skill-dir` 时仅增加技能文件复制。输出 `server` 的 command/args 填入当前宿主的 stdio 设置。
`--client` 原生接入分别安装 `.opencode/skills/mcpet` / `.claude/skills/mcpet`，不安装模型、不放开宿主审批。
技能内容不包含本机路径、凭证或用户台账；安装器只在本机输出具体服务路径。重跑会更新本技能文件，保留其他技能和未生成的文件。

重开或重新加载原 Agent 的项目会话后，可说“用 McPet 查瑞幸咖啡”“先查今天麦当劳优惠”“DeepSeek 娘穿麦麦套装”“切回默认套装”。宿主需同时发现技能并连接 MCP；仅复制 SKILL.md 不会创建工具。
外部写入按已展示的具体摘要取得明确确认；未知提交停止重发。自动提醒依赖现有宿主事件或已运行桌宠，不由技能建立额外后台调度。

## 验证与限制

2026-10-13：

- `python -m pytest tests/test_agent_skill.py tests/test_agent_host.py -q`：34 passed（17.30s），包含真实 stdio 连接、从其他项目运行已安装技能中的四个动作示例、21 个工具路由与实时 schema 匹配、无待确认订单时拒绝提交。
- skill-creator 的 `scripts/quick_validate.py .agents/skills/mcpet`：`Skill is valid!`；使用已安装 PyYAML 的开发解释器验证，未向产品依赖增加 PyYAML。
- `python -m compileall -q src scripts tests`、`git diff --check`：通过。
- 通用安装不读写品牌配置；原生安装保留其他 MCP、权限、hooks 和技能；同一技能可安装到相对或绝对目录，引用一并复制。
- 本项目已执行 `python -m src.agent_install --client both`，安装两种宿主的本机配置与技能；这些生成副本不提交。已打开的宿主需重新加载项目会话，原生信任/工具审批保持不变。

首轮保留在 `.tmp-test-data/agent-skill-first.log`：4 failed、29 passed、1 skipped；Windows 文本换行导致复制字节不同，安装器改为明确 LF；真实动作返回状态对象而不是 status=ok，测试改为核对真实角色和窗口状态。
该机器不允许测试创建真实符号链接，改用文件系统响应 fixture 验证拒绝分支，不宣称真实 Windows 链接验收。首轮技能验证因项目测试解释器缺少 PyYAML 未执行，随后用已有 PyYAML 的开发解释器完成。
复测日志为 `.tmp-test-data/agent-skill-second.log`，没有跳过项。测试数据、宿主目录和日志隔离到临时目录，不访问真实餐饮账号。
技能格式验证、安装回归、真实 stdio 协议和人工宿主对话分别记录；协议连接通过不等于模型已正确选择技能，也不等于真实订单或支付成功。
既有桌面 heartbeat 与素材断言 RED 保留，详见 [菜单与瑞幸验证](PET-MENU-LUCKIN-VALIDATION.md)。本轮不改桌宠运行状态与性能阈值。
