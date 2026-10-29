# McPet 🐳

> **[Anything Universe](https://github.com/songconmaisaix31-design#anything-universe)** · *Tools for agents. Room for anything.*
>
> 桌面入口：陪你工作、查看 Agent 状态，并通过 MCP 连接日常工具。
>
> 同系列：[swarm-anything](https://github.com/songconmaisaix31-design/swarm-anything) · [blockchain-anything](https://github.com/songconmaisaix31-design/blockchain-anything)

**余额有人盯，进度有人陪，干饭有人喊。**

McPet 是一只陪你工作的桌宠：看看 Agent 的会话状态和本机用量，提醒吃饭、喝咖啡，帮你查询麦当劳优惠与瑞幸商品。新用户默认由 DeepSeek 娘陪伴，也可以切换 ChatGPT 娘、给鲸鲸换上麦麦套装。

在桌面上，右键宠物打开菜单，选择和结果显示在气泡里；在 Agent 中，直接用正在聊的会话操作 McPet，沿用宿主的模型与计费。

[下载 v0.1.0](https://github.com/songconmaisaix31-design/mcpet/releases/tag/v0.1.0) · [完整使用指南](docs/USER-GUIDE.md) · [发行包快速开始](docs/RELEASE-QUICKSTART.md) · [反馈问题](https://github.com/songconmaisaix31-design/mcpet/issues)

## 和鲸鲸见个面

| 待机陪伴 | 忙碌工作 | 思考泡泡 |
|:---:|:---:|:---:|
| <img src="docs/media/deepseek/default-idle.gif" width="160" alt="DeepSeek 娘默认套装待机动画"> | <img src="docs/media/deepseek/default-working.gif" width="160" alt="DeepSeek 娘忙碌工作动画"> | <img src="docs/media/deepseek/default-thinking.gif" width="160" alt="DeepSeek 娘思考泡泡动画"> |
| **麦麦套装** | **炸薯条** | **换上麦麦套装** |
| <img src="docs/media/deepseek/maimai-idle.gif" width="160" alt="DeepSeek 娘麦麦套装待机动画"> | <img src="docs/media/deepseek/default-frying.gif" width="160" alt="DeepSeek 娘炸薯条循环动画"> | <img src="docs/media/deepseek/default-outfit.gif" width="160" alt="DeepSeek 娘换上麦麦套装动画"> |

<details>
<summary>展开更多动作：挥手、庆祝、吃饭、睡觉与双向换装</summary>

| 元气挥手 | 开心庆祝 | 吃饭 |
|:---:|:---:|:---:|
| <img src="docs/media/deepseek/default-greet.gif" width="160" alt="DeepSeek 娘挥手动画"> | <img src="docs/media/deepseek/default-happy.gif" width="160" alt="DeepSeek 娘庆祝动画"> | <img src="docs/media/deepseek/default-eating.gif" width="160" alt="DeepSeek 娘吃饭动画"> |
| **睡觉** | **垂头叹气** | **换回默认套装** |
| <img src="docs/media/deepseek/default-sleeping.gif" width="160" alt="DeepSeek 娘睡觉动画"> | <img src="docs/media/deepseek/default-error.gif" width="160" alt="DeepSeek 娘叹气动画"> | <img src="docs/media/deepseek/default-outfit-default.gif" width="160" alt="DeepSeek 娘换回默认套装动画"> |
| **向左跑** | **向右跑** | **麦麦套装右向状态** |
| <img src="docs/media/deepseek/default-run-left.gif" width="160" alt="DeepSeek 娘向左跑动画"> | <img src="docs/media/deepseek/default-run-right.gif" width="160" alt="DeepSeek 娘向右跑动画"> | <img src="docs/media/deepseek/maimai-run-right.gif" width="160" alt="麦麦套装穿装待机镜像动画"> |

麦麦套装的右向状态使用穿装待机的镜像。业务别名及缺少独立素材的状态使用对应已有动画，完整对应关系见[相册说明](assets/deepseek-recordings/SOURCE.md)。

</details>

<details>
<summary>展开早期鲸鲸九姿态（静态画面，使用时需本机导入）</summary>

| 待机 | 吃饭 | 思考 |
|:---:|:---:|:---:|
| <img src="docs/media/deepseek/default-ceta_nothing.gif" width="160" alt="早期鲸鲸待机静态姿态"> | <img src="docs/media/deepseek/default-ceta_eat.gif" width="160" alt="早期鲸鲸吃饭静态姿态"> | <img src="docs/media/deepseek/default-ceta_think.gif" width="160" alt="早期鲸鲸思考静态姿态"> |
| **被提起来** | **摸摸回应** | **余额告急** |
| <img src="docs/media/deepseek/default-ceta_pickup.gif" width="160" alt="早期鲸鲸被提起静态姿态"> | <img src="docs/media/deepseek/default-ceta_touch.gif" width="160" alt="早期鲸鲸摸摸回应静态姿态"> | <img src="docs/media/deepseek/default-ceta_nomoney.gif" width="160" alt="早期鲸鲸余额告急静态姿态"> |
| **元气登场** | **成功** | **失败** |
| <img src="docs/media/deepseek/default-ceta_cheerup.gif" width="160" alt="早期鲸鲸登场静态姿态"> | <img src="docs/media/deepseek/default-ceta_true.gif" width="160" alt="早期鲸鲸成功静态姿态"> | <img src="docs/media/deepseek/default-ceta_wrong.gif" width="160" alt="早期鲸鲸失败静态姿态"> |

导入步骤和素材权利说明见[早期姿态来源](assets/cetapet/SOURCE.md)。

</details>

图片来自用户提供的 GIF 动作全集，按实际不同画面展示 15 段动画与 9 张单帧姿态。[展示副本与来源](docs/media/deepseek/SOURCE.md)。

## 可以做什么

| 功能 | 使用方式 |
|---|---|
| 桌面陪伴 | 拖动、触摸、闲逛、休息；通过托盘隐藏、恢复或退出 |
| 角色与换装 | 切换 DeepSeek 娘 / ChatGPT 娘；保存默认套装 / 麦麦套装，播放炸薯条和换装动作 |
| 工作状态 | 查看已接入日志的会话进度、等待输入和错误；由后台活动驱动宠物动作 |
| 用量与余额 | 查看本机 token 台账、Orca 缓存额度及已配置的 DeepSeek 官方余额，标明来源和更新时间 |
| 麦当劳 | 查询优惠券、门店和实时报价，明确确认后领券、生成订单或申请撤单 |
| 瑞幸咖啡 | 选择门店、商品与规格，预览实付价，确认生成订单，查询取餐码与订单状态 |
| 营养记录 | 查询餐品营养，确认实际食用份数后记账，查看今日汇总 |
| 定时提醒 | 默认 11:30 饭点、15:00 咖啡时间；按设置进行只读查询与提醒 |

最新源码内置公开试用凭证，无需填写 MCP Token 就能试用麦当劳、瑞幸在线查询。试用操作使用共享账号；长期使用请配置自己的两家 Token，自己的配置优先。角色与皮肤可离线使用；进度和用量需要可读取的日志或宿主事件。订单生成后，由你进入品牌渠道完成付款。

## 快速开始

### Windows：下载后启动桌宠

1. 下载 [McPet-v0.1.0-windows-x64.zip](https://github.com/songconmaisaix31-design/mcpet/releases/download/v0.1.0/McPet-v0.1.0-windows-x64.zip)。
2. 解压完整文件夹，双击 **`Start-Pet.vbs`**。
3. 右键宠物，试试「角色与动作 → 麦麦套装」，或「设置 → 查看设置」。

便携包内置运行环境。保留 `McPet.exe`、`_internal` 和启动脚本的相对位置；直接双击 `McPet.exe` 会进入 MCP 服务模式。启动脚本不可用时，在解压目录运行：

```powershell
.\McPet.exe --desktop
```

首次使用不需要填写模型 Key。v0.1.0 下载包仍需自行填写餐饮凭证；最新源码已支持免 Token 在线试用。长期使用请在「设置 → 账号凭证」中填写自己的麦当劳、瑞幸 Token，余额查询按需配置，详见[账号设置](docs/USER-GUIDE.md#账号与本机配置)。

### Agent：接入正在使用的会话

宿主需要支持 **MCP stdio**。下载 [通用 Agent 包](https://github.com/songconmaisaix31-design/mcpet/releases/download/v0.1.0/McPet-v0.1.0-agent.zip)，解压后在其目录运行；已有源码也可使用同样命令：

```powershell
python -m pip install -r requirements-agent.txt
python -m src.agent_install
```

需要 Python 3.10+。将输出的 `server.command` 和 `server.args` 填入宿主的 MCP 设置，服务名填 `mcpet`，传输方式选择 stdio；重新加载会话并完成宿主的信任流程。然后说：

> 用 McPet 查看当前角色和设置。切到 DeepSeek 娘，穿麦麦套装。

Windows 便携包用户可运行 `.\McPet.exe --install` 导出同样的连接设置。MCP 服务由宿主启动；桌宠通过 `Start-Pet.vbs` 单独启动。两者使用相同的数据目录时，Agent 的动作和皮肤指令会传给已运行的桌宠。

技能安装、通用配置示例及 OpenCode / Claude Code 的可选原生适配见[Agent 接入步骤](docs/USER-GUIDE.md#在-agent-中使用)。

### 源码：运行桌面版

```powershell
git clone https://github.com/songconmaisaix31-design/mcpet.git
cd mcpet
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m src.main --desktop
```

桌面版使用 Python / PySide6。macOS、Linux 可使用通用 Agent 接入；桌面环境和托盘兼容性尚未完整验收。各平台虚拟环境命令见[使用指南](docs/USER-GUIDE.md#从源码运行)。

## 日常使用

| 想做什么 | 桌面入口 | 在 Agent 中可以这样说 |
|---|---|---|
| 给鲸鲸换衣服 | 角色与动作 → 默认套装 / 麦麦套装 | 「DeepSeek 娘穿麦麦套装」 |
| 看工作状态 | 会话与额度 → 会话进度 | 「用 McPet 看当前会话状态」 |
| 查优惠 | 麦当劳 → 查优惠券 | 「今天有什么麦当劳优惠？先查一下」 |
| 选咖啡 | 瑞幸咖啡 → 查找 / 选择门店 | 「帮我查附近瑞幸，选一杯拿铁，先预览价格」 |
| 记录午餐 | 营养台账 → 选择餐品 / 记账 | 「查询巨无霸营养，我吃了 1.5 份」 |
| 改提醒 | 设置 → 时间与位置 → 饭点 / 咖啡时间 | 「饭点改成 12:15，咖啡时间改成 15:30」 |

领券、下单、撤单和营养记账都会先展示具体摘要，再取得明确确认。默认订单护栏为单笔 100 元、每日 3 单；确认时还会复核金额。遇到 `delivery_unknown`，先到官方 App 核对订单，停止重复提交。

## 当前版本与使用边界

- **现行发行是 v0.1.0 Python/Qt 版。** Tauri 2、原创默认形象和系统密钥链的参赛版本处于 M0 阶段，进度见 [M0 报告](docs/contest/M0-REPORT.md)。个人凭证保存在本机 `.env`；公开试用凭证位于源码 `.env.trial`。
- 早期鲸鲸九姿态和全动作 GIF 相册属于后续源码功能，需要[本机导入或录制](docs/USER-GUIDE.md#可选动作与-gif-相册)，v0.1.0 发行包不附带这些本机文件。
- 本机用量只反映读取到的日志；厂商额度、余额和币种按各来源分别显示。未知数据保持未知，idle / Stop 表示会话状态，任务成功需要明确完成证据。
- 桌面定时提醒依赖桌宠运行；Agent 自动提醒依赖宿主活动。终端内 GIF 播放取决于宿主的图像资源能力。
- 真实账号订单、付款及完整宿主对话仍待人工验收；旧桌面心跳、前台性能和部分素材测试仍有历史 RED。各项范围见[验证记录](docs/README.md#当前交付记录)。

## 文档与反馈

| 文档 | 内容 |
|---|---|
| [完整使用指南](docs/USER-GUIDE.md) | 安装、菜单、Agent 接入、账号配置、餐饮流程、更新与常见问题 |
| [发行包快速开始](docs/RELEASE-QUICKSTART.md) | Windows 便携包和通用 Agent 包的首次启动 |
| [Agent 技术说明](docs/AGENT-HOST.md) / [技能说明](docs/AGENT-SKILL.md) | 工具、资源、宿主事件和技能复制 |
| [开发与验证](CONTRIBUTING.md) / [仓库结构](docs/REPOSITORY.md) | 开发环境、目录、测试命令与提交约定 |
| [开发交接](HANDOFF.md) / [当前状态](STATUS.md) | 接管入口、分支归属、已实现功能、阶段进度与待验收事项 |
| [全部文档](docs/README.md) | 功能说明、素材说明和历史验收记录 |

遇到问题可提交 [GitHub Issue](https://github.com/songconmaisaix31-design/mcpet/issues)，附上版本、系统、运行入口、复现步骤和脱敏后的错误信息；请先查阅[常见问题](docs/USER-GUIDE.md#常见问题)。

角色、动作与参考代码的来源和授权分别记录在[素材来源](assets/CREDITS.md)，各素材目录保留相应说明和许可证。本项目为社区开发作品；品牌信息、餐品价格与供应情况以官方渠道为准。[参赛声明](CONTEST_DECLARATION.md)。
