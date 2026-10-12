# 外部消息通知

AstrBot 插件：接收外部 HTTP 请求，将文本发送到指定会话。

## 配置

在插件管理中设置监听地址、端口、鉴权 Token 和默认目标会话。
默认监听地址为 `0.0.0.0`，默认端口为 `8080`，按部署情况填写。
会话格式为 `平台ID:消息类型:会话ID`。

## 请求格式

`POST /webhook`，请求头为 `Content-Type: application/json` 和
`Authorization: Bearer <你配置的Token>`。

```json
{"message": "任务已完成", "target": "平台ID:消息类型:会话ID"}
```

`message` 必填；`target` 可省略，使用默认目标。
可选 `title` 字段；不传时只发送正文。
成功返回 `{"success": true}`；失败返回 HTTP 错误状态和 `error`。
