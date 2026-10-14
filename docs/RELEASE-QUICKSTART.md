# McPet v0.1.0 · 鲸鲸来陪你啦 🐳

默认到岗的是 DeepSeek 娘，ChatGPT 娘也在小衣柜里等你。想吃饭、续杯咖啡，或看看工作的用量小账本？在原来的 Agent 里说一句就好。

从 [v0.1.0 下载页](https://github.com/songconmaisaix31-design/mcpet/releases/tag/v0.1.0) 的 Assets 区选择：Windows 桌宠用 `McPet-v0.1.0-windows-x64.zip`；已有 Python 的 Agent 用 `McPet-v0.1.0-agent.zip`。
完整菜单、账号配置、更新与常见问题见[项目使用文档](https://github.com/songconmaisaix31-design/mcpet#文档与反馈)。

## Windows 便携包

解压整个文件夹，再双击 **Start-Pet.vbs** 召唤桌宠。右键宠物找功能，选择、设置和结果都在小气泡里。
DeepSeek 娘的默认套装和麦麦套装随时可换；选过的角色、皮肤和提醒会记在你自己的小窝里。
McPet.exe 默认是 Agent 的 MCP 服务；直接双击它不会召唤宠物，用 Start-Pet.vbs 或显式 `McPet.exe --desktop`。

想让原 Agent 指挥桌宠？在这个文件夹里运行：

```powershell
.\McPet.exe --install
# 可选：安装到你使用 Agent 的项目，并复制技能
.\McPet.exe --install --project "你的项目" --skill-dir .agents/skills
# 也可选已有宿主的原生适配
.\McPet.exe --install --project "你的项目" --client opencode
.\McPet.exe --install --project "你的项目" --client claude
```

把输出的 server.command / server.args 填进当前 Agent 的 MCP 设置，服务名填 mcpet，传输方式选择 stdio；重新加载项目会话并完成宿主原生信任流程。移动整个文件夹后要重新接入。
Start-Pet.vbs 只启动桌宠；接入 Agent 不自动打开窗口，也不需要另买模型或另填模型 Key。

## 通用 Agent 包

适合已有 Python 3.10+ 的 Windows、macOS 或 Linux。解压后在该文件夹运行：

```text
python -m pip install -r requirements-agent.txt
python -m src.agent_install
```

同样填写 stdio 设置即可；要复制技能用 `--skill-dir "宿主的 skills 目录"`。桌宠需要另装 `requirements.txt` 中的 Qt，再显式运行 `python -m src.main --desktop`。

## 你可以这样叫我

- “今天有什么麦当劳优惠？先查，不领取。”
- “我想喝瑞幸拿铁，先帮我看门店和规格。”
- “DeepSeek 娘穿麦麦套装”“切回默认套装”“换 ChatGPT 娘陪我”。
- “看看我的额度小钱包”“今天吃了什么”“咖啡时间改成 15:30”。

饭点默认 11:30，咖啡时间默认 15:00。桌宠已运行且提醒开启时按时间/条件查询与提示；Agent 会话的提醒依赖宿主活动，不承诺宿主关闭时仍送达。
麦当劳、瑞幸的 Token 在「设置 → 账号凭证」的遮蔽输入气泡中填写，别贴进聊天。现行版本保存到用户数据目录的 .env（默认 ~/.mcpet），模型沿用宿主。没有凭证也能切角色、换衣服和使用已有日志的小账本。

最新源码提供[免 Token 在线试用](PUBLIC-TRIAL.md)，内置共享试用账号；长期使用请配置自己的 Token，个人配置优先。已上传的 v0.1.0 下载包保持原版本，仍需自行填写餐饮凭证。

## 首发的小边界

查价格与预览不会下单。领取、下单、撤单、记账都会按具体摘要取得明确确认；创建订单也不等于付款完成。提交结果未核实时先去官方订单核对，不要再点一遍。
本机用量只反映读取到的日志，厂商额度与账单按官方渠道核对；没读到的数据保持未知，任务成功需要明确完成证据。
这版验证覆盖离线业务、真实 stdio 与隔离桌宠启动；真实账号购买/付款及完整宿主对话仍待人工验收。旧桌面心跳性能和两项素材边界测试仍有未解决的 RED，不能把首发当成这些问题已经通过验收。

DeepSeek 素材许可证和其他素材出处随包保留；这是社区桌宠，不代表品牌官方产品。授权尚待确认的旧鲸鱼开发素材未放进这份包。
