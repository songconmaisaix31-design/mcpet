# v2 第一阶段验收报告

日期：2026-10-14。范围：`Pet.worry(Balance)` 样板；用户画风和声音确认仍待完成。

分支：`codex/reel-v2-worry-20261014`。SOURCE：`996c0ea551f648fefc8c1e396a8abb485a8f9649`，已成功推送至 origin；本验收报告单独提交。

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
