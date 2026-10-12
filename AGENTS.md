# McPet 项目执行约定

## 事实源与当前入口

先读 README、用户任务及对应 TASK/PRD/计划/Handoff。用户最新指令优先，任务文件是业务事实源。
当前默认是原 Agent 中的 MCP 服务；旧桌面仅显式 `--desktop`，旧 CLI 模型问答仅显式执行。
保持 Python 和既有目录，优先复用业务、Guard、台账与 provider。

## 执行与写入

小任务单 Agent。仅在任务能够按互斥文件路径并行时使用用户指定的 Orca CLI 流程：
主 Agent 一页计划、2–5 轨；每轨固定 1 Agent + 1 Worktree + 1 Branch + write_paths。
Worker 可读全仓，只写自域，跨轨只交 Handoff；开发、测试、文档及返修由同一 Worker 完成并 commit + push。
主 Agent 管计划/状态/决策/验收；全轨完成后交唯一集成 Agent 普通合并，领域问题退原 Worker。

不为并行重构，不构建自研调度器、Attempt、Manifest、Hash 或完成证明系统。
不 force push，不覆盖公共历史，不删除无法解释的文件或队友贡献。
可判断的歧义记录假设，真实阻塞再报告；逐阶段 commit，最终分支必须 push。

## 验证边界

核心路径、适用测试和构建通过后才报告完成。AI 生成、Mock 展示和未测代码不等于完成。
验证命令见 CONTRIBUTING.md；测试隔离数据与日志来源，不扩大到其他账号或无关对话。
禁止把真实凭证、本机宿主路径或个人台账提交到仓库。
外部写入保留明确确认与 delivery_unknown；不可自动重发未知提交。

保留首 RED/NOT_RUN/BLOCKED、旧性能阈值及历史证据。fixture、持久化、真实 stdio、
Qt/QTest、Windows foreground、真实账号效果和人工验收独立标注。
idle/Stop 不证明任务成功，本机用量不等于厂商额度；不能靠跳过或放宽断言刷绿。

最终只汇报完成内容、分支与 Commit SHA、验证命令和结果、真实剩余限制、
未执行或需要人工完成的操作。
