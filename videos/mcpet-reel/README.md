# McPet 新版发布视频

余额有人盯，进度有人陪，干饭有人喊。

当前交付是 v2 流水线第一步：`Pet.worry(Balance)` 风格样板。按用户最新要求，DeepSeek 娘使用早期 CeTaPet 仓库的形象与全部九种姿态，ChatGPT 娘使用白紫龙娘素材；鲸鲸看见小钱包降到 ¥4.37，短暂抖动后稳住，用气泡安慰你。配音由 Aliyun 百炼 CLI 的 `cosyvoice-v3-flash / longhua_v3` 合成；小敲击音效由代码生成。

这段展示使用演示余额，不调用用户模型余额或餐饮账号，不代表任何外部交易的实测。既有 Python 桌宠入口继续沿用，新视频工程独立放在本目录。

## 打开预览

需要 Node.js 22+、npm。首次安装：

```sh
npm ci
npm run dev -- --port=3327
```

打开 `http://localhost:3327/WorrySample`，点击播放，确认画风、语气、气泡大小和衰减动作。`predev` 会先生成时间轴和样板混音。源配音已随工程提供，预览不需要模型凭证。

`http://localhost:3327/CastPreview` 是双角色静态选角预览，两套形象均来自现有透明素材。ChatGPT 娘已接入 `Dragon` 组件，咖啡行为在后续阶段制作。

`http://localhost:3327/CeTaPetActions` 展示早期参考的完整九种姿态：待机、吃饭、思考、拖拽、点击、余额告急、登场、成功和失败。它们原本是九张静态 PNG，不是序列动画；`Pet` 的 `action` 参数可按原状态选择，余额样板使用 `nomoney` 姿态。

角色图片只在本地 `public/pet-skins/` 生成并被 Git 忽略。DeepSeek 来源为 [早期 CeTaPet 固定版本](https://github.com/kmjs1915/CeTaPet-AI-DeskTopPet-DeepSeek/tree/d0725b0e0aa58cd547c48b1681988ee708120d31)，其九张姿态按原目录结构复制，LICENSE 与 README 一并保留。ChatGPT 娘仍从现有 `assets/longniang` 提取睁眼待机帧。没有对应动作时用气泡表达；保留原始配色，不把静态图片称作连续动作动画。

独立重新导入九种姿态：

```sh
npm run import:cetapet
```

准备脚本优先复用已有早期参考缓存；缺少缓存时下载同一参考仓库，并校验固定提交。也可用 `MCPET_CETAPET_SOURCE` 显式指定检出该固定提交的本地仓库目录。路径不会写入生成产物。素材沿用当前项目 `assets/CREDITS.md` 的本地开发边界，不新增到发行包。

ChatGPT 娘也可自行导入本地皮肤包，包含透明图片 `chatgpt-idle.png`：

```powershell
$env:MCPET_REEL_SKIN_DIR = '你的本地皮肤包目录'
npm run dev -- --port=3327
```

导入路径只在进程环境内使用，不写入时间轴、源码或配置。请保留原皮肤包的来源与许可说明；本修订不新增提交角色图片。

删除 `timeline.json` 后，一条命令重新生成：

```sh
npm run prepare
```

`measure` 逐步求值同一个行为模型，直到弹簧静止、金额落定、气泡字打完、配音样本播完。`settleWhen` 只读物理与语义状态。`timeline.json` 是测量产物，Composition 使用它装配长度；Studio 的 metadata 也重新测量。只有 `src/design.ts` 的全局弹簧刚度与打字速率用于全片节奏调节，不手写场景时长。

## 语音与声音

```powershell
pwsh -File scripts/revoice.ps1
npm run prepare
```

重新配音需要本机配置好的 `bl`（Aliyun 百炼 CLI），调用会产生正常服务用量。脚本不保存凭证、不输出临时签名链接；不提供其他语音回退。`scripts/audio.ts` 从实测告急事件生成音效，使用 Remotion 随附 FFmpeg 两遍响度校正，输出样板混音及本地测量数据。

## 验证

```sh
npm run lint
npm test
npm run build
```

`build` 仅打包预览代码，不生成 MP4。测试覆盖自然完成条件、任意 seek 的确定性、余额单调递减、抖动衰减、全局节奏影响、测量产物及严格姿态锚点。1080×1920、左右 12%、底部 22% 的安全区由设计 token 与样板视觉检查约束。

## 当前验收边界

样板自然时长与响度见 [阶段验收报告](REPORT.md)。其余七个行为、全片 40–60 秒、跨行为逐帧连续性、最终混音和成片尚未验收。按用户任务书第九节，样板确认后进入后续制作；本阶段不自动渲染成片。可复用 `mcpet-reel` skill 在全流程收尾时交付。

## 字体与参考

**本视频软件使用 HarmonyOS Sans 字体**，附带未修改的简体中文常规字重及 [HarmonyOS Sans 字体许可](public/fonts/HarmonyOS-Sans-LICENSE.txt)。数字与代码使用 JetBrains Mono，附带 [OFL 许可](public/fonts/JetBrainsMono-OFL.txt)。这些字体许可独立于工程源码；角色素材的本地导入来源与文件保留方式见上文。没有复制参考项目的运行代码。Remotion 自身的使用条件见 [Remotion 许可](https://github.com/remotion-dev/remotion/blob/main/LICENSE.md)。

- [Remotion Skills](https://github.com/remotion-dev/skills)：已安装 best-practices、create、markup、studio；安装来源与内容锁记录在根目录 `skills-lock.json`。安装命令：`npx skills add remotion-dev/skills --skill remotion-best-practices remotion-create remotion-markup remotion-studio --agent claude-code --yes`。
- [OneTake](https://github.com/feitangyuan/OneTake)：学习持续存在的角色、道具与姿态锚点原则，不复制实现。
- [opus-video-prompts](https://github.com/joeseesun/opus-video-prompts)：原任务指定的 `video-prompt-library` 无法访问，改读同作者此库的长提示词与单形态生长范例；任务书的无预设时长规则优先。
- [HarmonyOS Sans 资源](https://developer.huawei.com/consumer/cn/design/resource-V1/)、[JetBrains Mono](https://github.com/JetBrains/JetBrainsMono)：字体下载来源。

样板画面中的“个人开源作品，与各公司官方无关”采用用户最新版任务书指定的原句。
