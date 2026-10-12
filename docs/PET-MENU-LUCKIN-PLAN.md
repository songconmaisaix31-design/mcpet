# 宠物菜单与瑞幸接入

用户要求：桌面只有宠物、右键小菜单和宠物气泡；原大面板功能移入分组菜单，时间/条件触发既有只读功能。继续支持任意 MCP stdio 宿主。

单 Agent 执行。菜单、气泡、主程序回调、调度与客户端生命周期共享状态，不拆并行轨道。

1. 复用 Streamable HTTP、SerialTasks、OrderGuard、营养台账和 DailySchedule，接入瑞幸官方服务。工具参数运行时按上游 inputSchema 验证；订单先预览、气泡确认、重新算价，仅发送一次。
2. 分组菜单覆盖角色/皮肤/动作、会话/用量/额度、麦当劳、营养、瑞幸、设置；气泡提供有限选项、输入、确认和支付链接。双击与托盘激活不创建 CompanionPanel。
3. 饭点查券/报价，咖啡时间查已选门店商品，既有后台事件驱动提醒。定时/条件路径不领取、不下单、不撤单、不记账。
4. 隔离 fixture 验证协议、菜单、取消与未知写入；真实 stdio、Qt 和 Windows 原生菜单/气泡分别记录。无瑞幸凭证时真实账号查询/支付标为 NOT_RUN；保留历史性能 RED。

业务协议来源：[瑞幸 AI 开放平台](https://open01.luckincoffeecdn.com/)，2026-10-13 读取公开工具文档。官方地址 `https://gwmcp.lkcoffee.com/order/user/mcp`，Bearer Token 在本机设置，不放入对话或 Git。
