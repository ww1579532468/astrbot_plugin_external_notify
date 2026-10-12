import asyncio
import hmac
import json
import time
import uuid

from aiohttp import web

from astrbot.api import logger
from astrbot.api.event import MessageChain
from astrbot.api.star import Context, Star, register
from astrbot.core.message.components import Plain
from astrbot.core.platform.astr_message_event import AstrMessageEvent
from astrbot.core.platform.astrbot_message import AstrBotMessage, MessageMember
from astrbot.core.platform.message_session import MessageSession
from astrbot.core.platform.message_type import MessageType
from astrbot.core.platform.platform_metadata import PlatformMetadata

PLUGIN_NAME = "astrbot_plugin_external_notify"
DEFAULT_LEVEL_PROMPTS = {
    1: (
        "将外部消息整理成简短的一句话通知用户，不重要内容可以完全忽略，允许不回复。"
        '只输出JSON对象，格式为{"notify":true,"text":"通知内容"}，不要输出代码围栏。'
        "无需通知时返回notify=false且text为空；需要通知时text必须非空。"
    ),
    2: (
        "将外部消息整理成简短的一句话通知用户，必须通知。"
        '只输出JSON对象，格式为{"notify":true,"text":"通知内容"}，不要输出代码围栏。'
        "notify必须为true，text必须非空。"
    ),
}


class ExternalNotifyEvent(AstrMessageEvent):
    """将外部通知包装为正常对话流程可处理的消息事件。"""

    def __init__(
        self,
        context: Context,
        session: MessageSession,
        platform_meta: PlatformMetadata,
        message: str,
    ):
        # 外部来源使用普通成员身份。
        message_obj = AstrBotMessage()
        message_obj.type = session.message_type
        message_obj.self_id = "external-notify-bot"
        message_obj.session_id = session.session_id
        if session.message_type == MessageType.GROUP_MESSAGE:
            message_obj.group_id = session.session_id
        message_obj.message_id = uuid.uuid4().hex
        message_obj.sender = MessageMember(
            user_id="external-notify", nickname="外部通知"
        )
        message_obj.message = [Plain(message)]
        message_obj.message_str = message
        message_obj.raw_message = message
        message_obj.timestamp = int(time.time())
        super().__init__(message, message_obj, platform_meta, session.session_id)
        self.session = session
        self.context_obj = context
        self.set_extra("_api_key_allow_admin_role", False)
        self.set_extra("external_notify", True)

    async def send(self, message: MessageChain) -> None:
        if message is None:
            return
        sent = await self.context_obj.send_message(self.session, message)
        if not sent:
            raise RuntimeError("外部通知回复发送失败")
        await super().send(message)

    async def send_streaming(self, generator, use_fallback: bool = False) -> None:
        async for chain in generator:
            await self.send(chain)


@register(PLUGIN_NAME, "ww", "外部消息通知", "1.1.4")
class ExternalNotifyPlugin(Star):
    def __init__(self, context: Context, config: dict | None = None):
        super().__init__(context)
        config = config or {}
        self.host = str(config.get("listen_host", "0.0.0.0")).strip() or "0.0.0.0"
        self.port = int(config.get("listen_port", 8080))
        self.token = str(config.get("token", "")).strip()
        self.default_target = str(config.get("default_target", "")).strip()
        self.ai_timeout = max(1, int(config.get("ai_timeout", 60)))
        self._requests: set[asyncio.Task] = set()
        self._runner: web.AppRunner | None = None

    async def initialize(self) -> None:
        # 等待监听成功再完成加载，启动失败交由 AstrBot 显示加载错误。
        await self._start_server()

    async def _start_server(self) -> None:
        # HTTP 服务随插件加载启动，卸载时统一清理。
        app = web.Application()
        app.router.add_post("/webhook", self._handle_webhook)
        self._runner = web.AppRunner(app)
        try:
            await self._runner.setup()
            site = web.TCPSite(self._runner, self.host, self.port)
            await site.start()
            logger.info(f"[{PLUGIN_NAME}] Webhook 服务已监听 {self.host}:{self.port}")
            if not self.token:
                logger.warning(f"[{PLUGIN_NAME}] Token 为空，0～2 级通知已关闭鉴权")
        except (Exception, asyncio.CancelledError):
            logger.exception(f"[{PLUGIN_NAME}] Webhook 服务启动失败")
            if self._runner:
                await self._runner.cleanup()
                self._runner = None
            raise

    async def _handle_webhook(self, request: web.Request) -> web.Response:
        # 低等级允许留空 Token；三级仍必须配置鉴权。
        if self.token:
            authorization = request.headers.get("Authorization", "")
            supplied_token = (
                authorization[7:].strip() if authorization.startswith("Bearer ") else ""
            )
            if not hmac.compare_digest(
                supplied_token.encode("utf-8"), self.token.encode("utf-8")
            ):
                return web.json_response(
                    {"success": False, "error": "鉴权失败"}, status=401
                )

        try:
            payload = await request.json()
        except Exception:
            return web.json_response(
                {"success": False, "error": "JSON 格式无效"}, status=400
            )
        if not isinstance(payload, dict):
            return web.json_response(
                {"success": False, "error": "请求正文必须是 JSON 对象"}, status=400
            )

        message = payload.get("message", "")
        level = payload.get("level", 0)
        source = payload.get("source", "")
        if not isinstance(message, str) or not message.strip():
            return web.json_response(
                {"success": False, "error": "message 必须是非空字符串"},
                status=400,
            )
        if type(level) is not int or level not in (0, 1, 2, 3):
            return web.json_response(
                {"success": False, "error": "level 必须是 0 到 3 的整数"},
                status=400,
            )
        if level == 3 and not self.token:
            return web.json_response(
                {"success": False, "error": "3 级必须配置鉴权 Token"},
                status=403,
            )
        if not isinstance(source, str):
            return web.json_response(
                {"success": False, "error": "source 必须是字符串"}, status=400
            )
        # 二级保留正文原样，AI 不可用时不加前缀、不压缩或截断。
        if level != 2:
            message = message.strip()
        requested_target = payload.get("target")
        if requested_target is not None and not isinstance(requested_target, str):
            return web.json_response(
                {"success": False, "error": "target 必须是字符串"}, status=400
            )
        target = (requested_target or self.default_target).strip()
        title = str(payload.get("title", "")).strip()
        if not target:
            return web.json_response(
                {"success": False, "error": "必须配置或提供目标会话"}, status=400
            )
        # 在调用模型或发送前使用 AstrBot 解析器检查会话格式。
        try:
            MessageSession.from_str(target)
        except ValueError:
            return web.json_response(
                {"success": False, "error": "目标会话格式无效"}, status=400
            )

        task = asyncio.current_task()
        self._requests.add(task)
        try:
            return await self._process_notification(
                message, target, title, source, level
            )
        finally:
            self._requests.discard(task)

    async def _process_notification(
        self, message: str, target: str, title: str, source: str, level: int
    ) -> web.Response:
        result = {
            "success": False,
            "status": "failed",
            "level": level,
            "notified": False,
        }
        text = f"【{title}】\n\n{message}" if title else message
        status = "sent"
        # 三级只交接到主对话，不等待或跟踪主对话的 AI 回复。
        if level == 3:
            result["handed_off"] = False
            try:
                self._submit_to_main(message, source, target)
            except Exception:
                logger.exception(f"[{PLUGIN_NAME}] 外部事件提交失败")
                result["reason"] = "handoff_error"
                text = ("主对话交接失败，原始消息：" + " ".join(message.split()))[:150]
                status = "fallback_sent"
            else:
                result.update(success=True, status="accepted", handed_off=True)
                return web.json_response(result)
        # 一、二级使用独立 AI，不读写主对话历史。
        elif level:
            try:
                notify, text = await asyncio.wait_for(
                    self._run_independent_ai(message, source, target, level),
                    timeout=self.ai_timeout,
                )
                if level == 1 and not notify:
                    result.update(success=True, status="ignored")
                    return web.json_response(result)
            except Exception as error:
                reason = "ai_timeout" if isinstance(error, TimeoutError) else "ai_error"
                logger.exception(f"[{PLUGIN_NAME}] 独立 AI 处理失败")
                result["reason"] = reason
                if level == 1:
                    result["error"] = "AI 处理失败"
                    return web.json_response(
                        result, status=504 if reason == "ai_timeout" else 502
                    )
                # 二级处理失败，仅发送请求中的原始正文。
                text = message
                status = "fallback_sent"

        try:
            sent = await self.context.send_message(target, MessageChain().message(text))
            if not sent:
                result["error"] = "目标平台未运行"
                return web.json_response(result, status=404)
        except Exception:
            logger.exception(f"[{PLUGIN_NAME}] 向目标会话发送消息失败")
            result["error"] = "消息发送失败"
            return web.json_response(result, status=500)

        result.update(success=True, status=status, notified=True)
        return web.json_response(result)

    def _submit_to_main(self, message: str, source: str, target: str) -> None:
        """提交外部事件，不在插件中运行或跟踪主对话 AI。

        Args:
            message: 外部消息正文。
            source: 来源说明，不作为认证身份或操作授权。
            target: 由请求指定或配置提供的目标会话。

        Raises:
            ValueError: 主会话或唤醒配置无效。
            RuntimeError: 目标平台不可用。
            asyncio.QueueFull: 框架事件队列无法接收事件。
        """
        session = MessageSession.from_str(target)
        platform = self.context.get_platform_inst(session.platform_id)
        if platform is None:
            raise RuntimeError("主对话所在平台未运行")
        text = f"来源为{source.strip() or '外部来源'}的消息：{message}"
        config = self.context.get_config(umo=str(session))
        if session.message_type == MessageType.FRIEND_MESSAGE and config.get(
            "platform_settings", {}
        ).get("friend_message_needs_wake_prefix", False):
            prefix = next(
                (
                    value
                    for value in config.get("wake_prefix", [])
                    if isinstance(value, str)
                ),
                None,
            )
            if prefix is None:
                raise ValueError("主对话未配置所需的唤醒前缀")
            text = prefix + text
        event = ExternalNotifyEvent(self.context, session, platform.meta(), text)
        self.context.get_event_queue().put_nowait(event)

    async def _run_independent_ai(
        self, message: str, source: str, target: str, level: int
    ) -> tuple[bool, str]:
        # 跟随目标会话的 AstrBot 模型配置，不单独指定模型。
        provider_id = await self.context.get_current_chat_provider_id(target)
        system_prompt = DEFAULT_LEVEL_PROMPTS[level]
        # 系统提示词单独传入；来源和正文仅作为待处理数据。
        prompt = f"来源为（{source.strip() or '外部来源'}）的消息：\n{message}"
        response = await self.context.llm_generate(
            chat_provider_id=provider_id,
            prompt=prompt,
            system_prompt=system_prompt,
            contexts=[],
            tools=None,
        )
        if response.tools_call_name:
            raise ValueError("独立 AI 不允许调用工具")
        # 固定 JSON 协议用于控制是否通知；正常 AI 输出保持简短单行。
        raw = response.completion_text.strip()
        if raw.startswith("```") and raw.endswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        decision = json.loads(raw)
        if not isinstance(decision, dict) or type(decision.get("notify")) is not bool:
            raise ValueError("AI 通知决策格式无效")
        text = decision.get("text", "")
        if not isinstance(text, str):
            raise ValueError("AI 通知文本格式无效")
        text = " ".join(text.split())[:150]
        if (level >= 2 or decision["notify"]) and not text:
            raise ValueError("AI 通知文本为空")
        return decision["notify"], text

    async def terminate(self) -> None:
        # 取消插件自身请求并关闭监听，不撤回已交给主对话的事件。
        active = [task for task in self._requests if task is not asyncio.current_task()]
        for task in active:
            task.cancel()
        if active:
            await asyncio.gather(*active, return_exceptions=True)
        if self._runner:
            await self._runner.cleanup()
            self._runner = None
