---
name: task-notify
description: 用户要求“无人值守”“完成后通知我”“做完通知我”或发送通知消息时使用；支持远程 Webhook 和本机 AstrBot 两种方式。
---

# 任务通知

默认使用本机通知；用户明确指定“远程通知”或“服务器通知”时使用远程 Webhook。只发送所选方式，不同时发送两份，也不自动切换方式。

任务完成并核验后、最终答复前，发送一次简短中文通知，说明任务和真实结果。失败或需要用户处理时如实通知；用户取消通知时不发送。用户要求直接发送消息时，按指定正文发送。

运行对应脚本，将路径替换为实际技能安装路径：

```text
python <技能目录>/scripts/webhook.py --message "通知正文"
python <技能目录>/scripts/local.py --message "通知正文"
```

首次使用手动填写技能目录中的 `config.txt`（JSON 格式），上半部分 `local` 为本机配置，下半部分 `server` 为服务器配置：

- `local.target`：本机会话，格式为 `平台ID:消息类型:会话ID`。
- `local.astrbot_config`：本机配置文件路径，留空使用 `~/.astrbot/data/cmd_config.json`；Windows 路径建议用 `/`。
- `server.webhook_url`：完整 Webhook 地址。
- `server.webhook_token`：鉴权 Token，无鉴权时留空。

远程服务需支持 `message`、`level: 0`、`source` 请求字段，并配置默认接收目标。本机方式要求 AstrBot 正在运行、目标平台在线，且版本支持 `/api/v1/im/messages`；脚本仅调用本机接口，不修改配置。

退出码为 0 表示接口确认发送调用完成，不代表用户已阅读。失败或超时时如实说明，不自动重发。不要输出凭据；分享或上传技能前清空 `config.txt` 中的个人配置值。
