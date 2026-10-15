# 外部消息通知

接收 webhook 消息转交AI。

仅需本机直接发送时，可单独使用附带 skill 的 `local.py` 调用 AstrBot 内置接口，无需安装本插件。
该方式仅支持原文发送。需求调用AI时仍需安装本插件。

## 配置

| 配置项 | 说明 |
| --- | --- |
| `listen_host` | 监听地址，默认 `0.0.0.0` |
| `listen_port` | 监听端口，默认 `8080` |
| `token` | 鉴权 Token；留空关闭 |
| `default_target` | 默认目标，格式为 `平台ID:消息类型:会话ID` |
| `ai_timeout` | 独立 AI 超时秒数，默认 `60` |

修改配置后重载插件生效。公网使用建议配置 Token 和 HTTPS。

## 发送消息

向 `POST /webhook` 发送 JSON，请求头为 `Content-Type: application/json`。
配置 Token 时，添加 `Authorization: Bearer <Token>`。

```json
{
  "message": "任务已完成",
  "level": 2,
  "source": "codex"
}
```

`message` 必填；`level` 默认0，`source` 可选。可用 `target` 指定其他目标，否则使用默认目标；`title` 可选，仅0级使用。

### curl 示例

直接修改地址、`YOUR_TOKEN` 和 JSON 中的消息内容后运行；`target` 留空使用默认目标，也可以填写指定会话。

```bash
curl http://127.0.0.1:8080/webhook \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
        "message": "任务已完成",
        "level": 2,
        "source": "codex",
        "target": ""
      }'
```

地址中的 IP 和端口应与实际部署一致。未配置 Token 的0～2级请求可以删除 Authorization 那一行。
以上换行写法适用于 Bash、WSL 或 Git Bash。不要在行末的 `\` 后添加空格。
请求超时或连接中断不代表服务端未处理，不要盲目重发，以免重复通知。

## 消息等级

| 等级 | 行为 |
| --- | --- |
| 0 | 直接转发 |
| 1 | 独立AI,失败不通知。 |
| 2 | 独立AI，失败返回原文。 |
| 3 | 交给主对话正常处理。 |

## 返回结果

`status` 为 `sent`（已调用发送接口）、`ignored`（无需通知）、`fallback_sent`（兜底发送）、`accepted`（3级已提交）或 `failed`（失败）。
`accepted` 不代表 AI 已回复；`sent` 不代表用户已阅读。插件不自动重试，也不在 HTTP 响应中返回 AI 回复正文。

## Codex task-notify skill

技能源码位于 [skills/task-notify](skills/task-notify)，支持本机 AstrBot 与远程 Webhook，默认使用本机通知。

将该文件夹复制到 `~/.codex/skills/`，填写其中的 `config.txt` 即可使用。仓库中配置值均为空，不包含个人凭据。

本机独立发送只需填写 `local` 配置，并保证 AstrBot 正在运行、目标平台在线，且支持 `/api/v1/im/messages`：

```text
python <技能目录>/scripts/local.py --message "任务已完成"
```

本机脚本只直接发送正文，不接受 `--level`，不调用 AI。使用插件 Webhook 时，`webhook.py` 支持 `--level 0～3`（默认 0）及可选 `--target`。
