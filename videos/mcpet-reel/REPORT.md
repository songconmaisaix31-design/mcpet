# v2 第一阶段验收报告与形象返修

日期：2026-10-14。范围：`Pet.worry(Balance)` 样板；用户画风和声音确认仍待完成。

分支：`codex/reel-v2-worry-20261014`。初版 SOURCE：`996c0ea551f648fefc8c1e396a8abb485a8f9649`，已成功推送至 origin；本验收报告单独提交。以下初版结果保留，最新形象修订见末节。

## 完成内容

- 按序安装并阅读 Remotion 技能及连续性、字体、音频规则；先启动 Studio，再制作行为样板。
- 原创几何鲸鲸、黑蓝/金/告急红、1080×1920 竖屏。余额从 ¥12.80 单调滚落到 ¥4.37，短暂抖动带指数衰减；没有业务动作的表达用气泡。
- Aliyun CLI 真实合成龙华配音，源 WAV 为 24 kHz 单声道、158222 samples。代码生成小敲击，触发点由余额首次低于 ¥5 自然测出。
- `Behavior` 协议、无帧数比较的完成条件、严格姿态接棒校验、生成式时间轴及独立行为预览。当前仅注册 `WorrySample`。

## 验证结果

- `npm run prepare`：PASS；测量产物 207 frames / 30 fps = 6.900 秒；完成条件包含物理静止、文字完成和源配音播放完成。
- 样板混音两遍校正后的 FFmpeg 实测：−13.95 LUFS，−1.48 dBTP。仅证明本样板混音；全片响度仍待最终装配验证。
- `npm run lint`：PASS，ESLint 与 TypeScript。
- `npm test`：6 项 PASS，覆盖自然完成、确定性、递减金额、衰减抖动、全局打字速度与姿态契约。
- `npm run build`：PASS，只生成预览 bundle。
- Studio 实际页面自动检查：两个指定字体已加载、鲸鲸存在、播放后出现 ¥4.37 与完整气泡。已查看开始和气泡完成时的页面截图，关键信息位于安全区内。不是 MP4 渲染，不替代用户试听与画风验收。
- 删除 `timeline.json` 后执行 `npm run prepare`：PASS；重新生成的字节与原产物完全一致。`git diff --cached --check` 修正上游许可空格后 PASS；SOURCE 分支推送 PASS。

## 首次失败与现实差异

1. 用户指定 `npx remotion skills add` 首次退出 1：`could not determine executable to run`。使用 Remotion 现行 `npx skills add remotion-dev/skills ...` 成功安装四个技能。
2. `joeseesun/video-prompt-library` clone 返回 `Repository not found`。补读同作者 `opus-video-prompts`；没有复制其中代码，也没有采用其预设节拍时长。
3. 配音首轮请求为 48 kHz，带 instruction/seed，返回 HTTP 400、`InvalidParameter`、engine 428；精简参数后 24 kHz 请求成功。未通过单变量实验确认首轮究竟是哪一个参数导致失败。
4. 编辑期间 Studio 在生成 JSON 尚未落盘时出现过缺少模块的构建错误；产物生成后重新构建成功，最终类型检查和 bundle 通过。
5. 自动审批拦截了使用 `Start-Process` 额外打开浏览器的命令，未提供具体原因。Studio 服务仍可访问；使用独立临时浏览器检查该 Studio 页面。用户可自行打开预览链接。
6. 首次暂存差异检查发现上游 OFL 文本的一处行末空格。仅移除该空格，许可内容和字体文件不变；重新检查通过。

页面截图与下载缓存保留在本地忽略目录；首次失败按本节保留。临时签名链接不写入仓库。

## 待用户确认 / 未执行

任务书第九节要求“样板通过后，其余行为并行铺开”及“每步只拉起 Remotion Studio 本地预览，我现场确认后再进下一步”。因此本阶段停在可审核样板。

其余七个行为、八段共同姿态连续性、全片 40–60 秒、饭点/券/咖啡/账本/Star 展示、最终 −14 LUFS、成片输出和 `mcpet-reel` 收尾 skill 均未执行。当前演示余额不是真实余额查询，既有餐饮/模型账号功能也未新增验收。

## 2026-10-14 形象修订

用户最新要求：“用 deepseek 娘的形象和 chatgpt 娘的形象做视频”。此要求覆盖此前样板的几何角色风格；仍保留先确认样板、后制作全片的流程。

- `WorrySample` 改用既有蓝发 DeepSeek 娘透明待机形象，新增 `Dragon` 组件使用白紫 ChatGPT 龙娘。`CastPreview` 是两套形象同框的静态选角页，未增加硬编码的叙事时长。
- 保留皮肤自身配色，UI 配色沿用黑蓝、金、告急红；没有对应表情或动作时由气泡表达，不反复眨眼或换不同姿态帧制造抖动。
- 本机准备脚本从既有 DeepSeek 待机页与 ChatGPT 待机行提取首帧，图片只生成到 Git 忽略目录。可从显式指定的用户本地皮肤包导入，不新增向仓库分发形象文件。
- 实际 Studio 页面检查：DeepSeek 图像 192×192、ChatGPT 图像 192×208，均成功加载；两套形象同框、字体加载、¥4.37 与完整气泡播放通过。已目视检查截图，透明背景与安全区正常。没有自动打开额外浏览器窗口或渲染 MP4。
- `npm run prepare` 与 `npm run measure`：PASS；样板仍为 207 frames / 6.9 秒，原 Aliyun 配音及样板混音保持 −13.95 LUFS。
- `npm run lint`、`npm test`（7 项）、`npm run build`：PASS。两套提取结果与源图集对应首帧的 RGBA 逐像素相同，含透明与可见区域。
- 隔离的用户皮肤包 fixture 导入后单独运行 `scripts/skins.test.ts`：1 PASS，导入图与输出图像素相同；未读取其他用户目录。
- 首次测试 **6 PASS / 1 RED**：Remotion 随附 FFmpeg 缺少 `rawvideo` 输出 muxer；保留此错误，改用 PNG 管道及 PNG 解码后原样比较 RGBA，重跑 **7 PASS**。没有放宽像素相等断言。

形象修订 SOURCE：`8e9cec3d4e594b4ecad028847bbddbf2408792c4`。`git diff --cached --check`：PASS；本地皮肤图片未被暂存。推送结果见交付消息。

限制：当前采用静态睁眼待机帧与外层衰减动作；没有新增角色表情动画。ChatGPT 咖啡行为、其余七段与最终成片仍待样板确认后制作。
