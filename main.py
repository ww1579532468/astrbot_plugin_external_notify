import asyncio
import hmac

from aiohttp import web

from astrbot.api import logger
from astrbot.api.event import MessageChain
from astrbot.api.star import Context, Star, register

PLUGIN_NAME = "astrbot_plugin_external_notify"


@register(PLUGIN_NAME, "ww", "外部消息通知", "1.0.0")
class ExternalNotifyPlugin(Star):
    def __init__(self, context: Context, config: dict | None = None):
        super().__init__(context)
        config = config or {}
        self.host = str(config.get("listen_host", "0.0.0.0")).strip() or "0.0.0.0"
        self.port = int(config.get("listen_port", 8080))
        self.token = str(config.get("token", "")).strip()
        self.default_target = str(config.get("default_target", "")).strip()
        self._runner: web.AppRunner | None = None
        self._server_task = asyncio.create_task(self._start_server())

    async def _start_server(self) -> None:
        app = web.Application()
        app.router.add_post("/webhook", self._handle_webhook)
        self._runner = web.AppRunner(app)
        try:
            await self._runner.setup()
            site = web.TCPSite(self._runner, self.host, self.port)
            await site.start()
            logger.info(f"[{PLUGIN_NAME}] Webhook listening on {self.host}:{self.port}")
        except Exception:
            logger.exception(f"[{PLUGIN_NAME}] Failed to start Webhook server")
            if self._runner:
                await self._runner.cleanup()
                self._runner = None

    async def _handle_webhook(self, request: web.Request) -> web.Response:
        if not self.token:
            return web.json_response(
                {"success": False, "error": "plugin token is not configured"},
                status=503,
            )

        authorization = request.headers.get("Authorization", "")
        supplied_token = authorization[7:].strip() if authorization.startswith("Bearer ") else ""
        if not hmac.compare_digest(supplied_token, self.token):
            return web.json_response(
                {"success": False, "error": "unauthorized"}, status=401
            )

        try:
            payload = await request.json()
        except Exception:
            return web.json_response(
                {"success": False, "error": "invalid JSON"}, status=400
            )
        if not isinstance(payload, dict):
            return web.json_response(
                {"success": False, "error": "JSON object required"}, status=400
            )

        message = str(payload.get("message", "")).strip()
        target = str(payload.get("target") or self.default_target).strip()
        title = str(payload.get("title", "")).strip()
        if not message:
            return web.json_response(
                {"success": False, "error": "message is required"}, status=400
            )
        if not target:
            return web.json_response(
                {"success": False, "error": "target is required"}, status=400
            )

        text = f"【{title}】\n\n{message}" if title else message
        try:
            sent = await self.context.send_message(target, MessageChain().message(text))
            if not sent:
                return web.json_response(
                    {"success": False, "error": "target platform is not running"},
                    status=404,
                )
        except Exception:
            logger.exception(f"[{PLUGIN_NAME}] Failed to send message to target")
            return web.json_response(
                {"success": False, "error": "failed to send message"}, status=500
            )

        return web.json_response({"success": True})

    async def terminate(self) -> None:
        if self._server_task and not self._server_task.done():
            self._server_task.cancel()
            await asyncio.gather(self._server_task, return_exceptions=True)
        if self._runner:
            await self._runner.cleanup()
            self._runner = None
