"""
StreamService — Step3 窗口/解码初始化封装（经 step3_router → step3_xsrp）。
"""

from dataclasses import dataclass
from typing import Any, Callable, Optional

from ..auth.api import StreamingCredentials
from ..core.logger import get_logger
from ..discovery.models import ConsoleTarget
from ..task.task_context import AgentTaskContext, XboxInfo


@dataclass
class MediaSession:
    task_id: str
    context: AgentTaskContext
    decode_mode: str = "auto"

    @property
    def frame_capture(self):
        return self.context.frame_capture

    @property
    def sdl_window(self):
        return self.context.sdl_window


class XHomeStreamService:
    """Step3 媒体层：经 router 调用 xsrp/cloud Step3。"""

    def __init__(self):
        self.logger = get_logger("stream_service")

    async def open_stream(
        self,
        credentials: StreamingCredentials,
        console: ConsoleTarget,
        task_id: str,
        window_manager: Any = None,
        decode_mode: str = "auto",
        check_cancel: Optional[Callable[[], bool]] = None,
        report_progress: Optional[Callable] = None,
        source_context: Optional[AgentTaskContext] = None,
    ) -> MediaSession:
        from ..automation.step3 import step3_execute_xsrp_init

        step3_streaming_init = step3_execute_xsrp_init
        from ..vision.decode_strategy import resolve_decode_mode

        if source_context is not None:
            context = source_context
            context.task_id = task_id
        else:
            context = AgentTaskContext(
                task_id=task_id,
                streaming_account_id=credentials.streaming_account_id,
                streaming_account_email=credentials.email,
                streaming_account_password=credentials.password,
                streaming_account_auto_code=credentials.auto_code,
            )
            context.microsoft_tokens = credentials.microsoft_tokens
            context.xbox_tokens = credentials.xbox_tokens

        context.assigned_xbox = XboxInfo(
            id=console.id,
            name=console.name,
            ip_address=console.ip_address,
            live_id=console.live_id,
            mac_address=console.mac_address,
            play_path=console.play_path,
            power_state=console.power_state,
            console_type=console.console_type,
        )

        resolved_mode = resolve_decode_mode(decode_mode)
        context.modules_decode_mode = resolved_mode  # type: ignore[attr-defined]

        async def _report(*args, **kwargs):
            if report_progress:
                await report_progress(*args, **kwargs)

        from ..automation.step3 import is_xsrp_stream_media_ready

        if is_xsrp_stream_media_ready(context):
            self.logger.info(
                "Step3 已在 Step2 链完成 (task=%s)，跳过 open_stream 重复初始化",
                task_id[:8],
            )
            return MediaSession(
                task_id=task_id,
                context=context,
                decode_mode=resolved_mode,
            )

        try:
            result = await step3_streaming_init(
                context,
                check_cancel or (lambda: False),
                _report,
            )
            if not result.success:
                raise RuntimeError(result.message or "Stream init failed")
        except Exception:
            from .cleanup import close_media_context

            await close_media_context(context, self.logger)
            raise

        return MediaSession(
            task_id=task_id,
            context=context,
            decode_mode=resolved_mode,
        )

    async def reconnect(self, media: MediaSession) -> bool:
        from ..xbox.stream_recovery import reconnect_input_channel

        try:
            return await reconnect_input_channel(media.context, self.logger)
        except Exception as exc:
            self.logger.error("Reconnect failed: %s", exc)
            return False

    async def close(self, media: MediaSession) -> None:
        await self.close_context(media.context)

    async def close_context(self, context: AgentTaskContext) -> None:
        from .cleanup import close_media_context

        await close_media_context(context, self.logger)
