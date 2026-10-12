# 外部消息通知

AstrBot 插件：接收外部 HTTP 请求，将文本发送到指定会话。

## 配置

在插件管理中设置监听地址、端口、鉴权 Token 和默认目标会话。
默认监听地址为 `0.0.0.0`，默认端口为 `8080`，按部署情况填写。
会话格式为 `平台ID:消息类型:会话ID`。

## 请求格式

`POST /webhook`，请求头为 `Content-Type: application/json` 和
`Authorization: Bearer <你配置的Token>`。

配置了 Token 时，请求必须提供正确的 Bearer Token；Token 留空或仅含空格时跳过鉴权，
请求不需要提供 Authorization 请求头。公网关闭鉴权后，任何能访问接口的人都可以调用。

```json
{"message": "任务已完成", "target": "平台ID:消息类型:会话ID"}
```

`message` 必填；`target` 可省略，使用默认目标。
可选 `title` 字段；不传时只发送正文。
成功返回 `{"success": true}`；失败返回 HTTP 错误状态和 `error`。

此版本尚未加入 AI 处理和数字处理等级。
公网部署建议使用 HTTPS，避免明文传输 Token。
请勿将部署凭据、实际会话标识或运行数据提交到仓库。

## 许可证

本项目采用 Creative Commons Attribution 4.0 International（CC BY 4.0）协议。
完整条款见 `LICENSE`。署名作者：ww。
