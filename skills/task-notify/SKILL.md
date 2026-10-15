---
name: task-notify
description: 用户要求“无人值守”“完成后通知我”“做完通知我”“向我的微信/QQ发送消息”或发送通知消息时使用；支持远程 Webhook 和本机 AstrBot 两种方式。
---

# 任务通知

默认使用本机通知；用户明确指定“远程通知”或“服务器通知”时使用远程 Webhook。只发送所选方式，不同时发送两份，也不自动切换方式。

任务完成并核验后、最终答复前，发送一次简短中文通知，说明任务和真实结果。失败或需要用户处理时如实通知；用户取消通知时不发送。用户要求直接发送消息时，按指定正文发送。

运行对应脚本，将路径替换为实际技能安装路径：

```text
python <技能目录>/scripts/webhook.py --message "通知正文" --level 0
python <技能目录>/scripts/local.py --message "通知正文"
```

首次使用手动填写技能目录中的 `config.txt`（JSON 格式），上半部分 `local` 为本机配置，下半部分 `server` 为服务器配置：

- `local.target`：本机会话，格式为 `平台ID:消息类型:会话ID`。
- `local.astrbot_config`：本机配置文件路径，留空使用 `~/.astrbot/data/cmd_config.json`；Windows 路径建议用 `/`。
- `server.webhook_url`：完整 Webhook 地址。
- `server.webhook_token`：鉴权 Token，无鉴权时留空。

本机独立发送不需要安装通知插件：`local.py` 直接调用 AstrBot 内置接口，仅支持相当于 `0` 级的原文发送，不调用 AI，也不进入主对话。无需传入 `--level`；明确指定本机 1～3 级时，说明不支持，不自动切换远程或安装插件。

以下等级仅用于插件 Webhook。远程脚本支持 `--level 0～3`，默认 `0`；可加 `--target "平台ID:消息类型:会话ID"` 指定会话，省略则使用服务端默认目标。

| level | 行为 |
| --- | --- |
| 0 | 直接转发原文。 |
| 1 | 由独立 AI 处理，处理失败时不通知。 |
| 2 | 由独立 AI 处理，处理失败时转发原文。 |
| 3 | 提交给目标会话的主对话处理，需配置鉴权 Token。 |

远程服务需支持 `message`、`level`、`source` 和可选 `target` 字段。本机方式要求 AstrBot 正在运行、目标平台在线，且版本支持 `/api/v1/im/messages`；脚本仅调用本机接口，不修改配置。

退出码为 0 表示接口已成功处理请求；`sent` / `fallback_sent` 表示调用发送接口，`ignored` 表示 AI 判断无需通知，`accepted` 表示已提交主对话，不代表 AI 已回复或用户已阅读。失败或超时时如实说明，不自动重发。不要输出凭据；分享或上传技能前清空 `config.txt` 中的个人配置值。
