# 免 Token 在线试用

最新源码内置麦当劳、瑞幸的公开试用凭证，位于项目根目录 `.env.trial`。用户已明确确认将两枚真实 Token 一起提交公开仓库，供下载者试用在线餐饮接口。

## 使用方式

下载源码并完成依赖安装后，直接启动桌宠或将 McPet 接到当前 Agent。无需另外填写 MCP Token，可查询两家服务的餐饮能力。试用请求使用共享账号，领取优惠券、创建或撤销订单仍需明确确认；付款由用户在品牌渠道完成。

长期使用请配置自己的麦当劳、瑞幸 Token：桌宠右键「设置 → 账号凭证」，或在本机 `.env` 填写 `MCD_MCP_TOKEN`、`LUCKIN_MCP_TOKEN`。配置优先级为进程环境变量、用户数据目录 `.env`、项目 `.env`、公开 `.env.trial`。未填写或保留占位符的餐饮字段使用试用凭证，已填写的个人配置优先。

`mcpet_settings` 返回 `mcd_credential_mode` 和 `luckin_credential_mode`；`trial` 表示正在使用公开试用凭证，`personal` 表示使用其他个人凭证。输出不返回 Token。公开凭证失效、服务限流和接口错误均直接报告，不替换账号重试。

## 发行范围

目前公开 v0.1.0 下载包保持原版本，需要自行配置餐饮 Token。新的源码构建会将 `.env.trial` 加入通用 Agent 包和 Windows 包；本机 `.env`、宿主配置和个人台账不进入发行包。

## 验证命令

```powershell
.\.venv\Scripts\python.exe -X utf8 scripts/verify_trial_credentials.py --online mcd
.\.venv\Scripts\python.exe -X utf8 scripts/verify_trial_credentials.py --online luckin
.\.venv\Scripts\python.exe -X utf8 scripts/verify_trial_credentials.py --archive
.\.venv\Scripts\python.exe -X utf8 -m compileall -q src scripts
git diff --check
```

2026-10-15 实际结果：两家 initialize 与 tools/list 成功，分别返回 35 和 8 个工具；麦当劳 `now-time-info` 实际调用成功。使用真实凭证通过现有设置接口保存到隔离用户目录，重新加载后保留个人配置优先级，输入两侧空格在请求前正常清理。真实 MCP stdio 的设置查询正常，输出不含两枚 Token。通用 Agent 验证包成功生成，含公开试用配置、排除个人 `.env`，解压后的全新用户目录可以加载两家试用凭证。验证使用真实文件、实际子进程和 HTTP，没有使用 mock 或伪造凭证。

本次没有生成、撤销或支付订单，没有发布新版下载包，没有执行旧 mock 用例或完整 GUI 性能验收。试用凭证的有效期和服务限流由两家服务决定。首轮实际结果保存在本机 `.tmp-test-data/credential-binding/`，不进入 Git。

带空格凭证的脱敏检查首轮为 RED，保存在 `luckin-final.log` 和 `stdio-archive-final.log`；最终验证按服务隔离目录保存，检查真实 Token 的规范化值被完整遮蔽。首轮记录保留。
