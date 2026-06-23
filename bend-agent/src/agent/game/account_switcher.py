"""
游戏账号切换器
==============

功能说明：
- 管理多个游戏账号
- 自动化账号切换流程（位置索引 + Streaming 场景卡点）
- 切换后进 FC UT 主菜单
- 支持添加新用户（场景10+ 小键盘登录）

技术实现说明：
- 场景6「您是谁」列表顺序随最近登录变化，运行时 OCR 按 gamertag 定位
- 场景 3/5/6 用 StreamingSceneDetector 校验 Xbox 系统 UI
"""

import asyncio
import re
from typing import Optional, Dict, List, Any, Callable, Awaitable, Tuple
from dataclasses import dataclass
from enum import Enum
import time

from ..core.logger import get_logger
from ..core.paths import get_logs_dir_fallback
from ..debug.automation_trace import (
    capture_entry_scene_survey,
    get_scene_capture_session,
    log_gamepad_input,
)
from ..vision.frame_utils import frame_to_bgr_ndarray


def _extract_frame_image(frame: Any) -> Optional[Any]:
    """从 Frame/ndarray 提取 BGR 图像；禁止对 ndarray 误用 .data。"""
    return frame_to_bgr_ndarray(frame)


class AccountStatus(Enum):
    """账号状态枚举"""
    UNKNOWN = "unknown"
    AVAILABLE = "available"
    LOGGING_IN = "logging_in"
    LOGGED_IN = "logged_in"
    LOGGING_OUT = "logging_out"
    LOGGED_OUT = "logged_out"
    ERROR = "error"


@dataclass
class GameAccount:
    """游戏账号数据"""
    account_id: str
    gamertag: str
    email: Optional[str] = None
    password: Optional[str] = None
    xuid: Optional[str] = None
    position_index: int = 0
    is_new_user: bool = False
    host_display_name: Optional[str] = None
    status: AccountStatus = AccountStatus.UNKNOWN
    last_login: Optional[float] = None
    matches_today: int = 0
    max_matches_per_day: int = 3

    def is_available(self) -> bool:
        return self.matches_today < self.max_matches_per_day

    def needs_credential_login(self) -> bool:
        """新用户且已配置凭据时走微软登录页。"""
        return bool(
            self.is_new_user and self.email and self.password
        )

    def mark_login(self):
        self.status = AccountStatus.LOGGED_IN
        self.last_login = time.time()

    def increment_matches(self):
        self.matches_today += 1

    def reset_daily_count(self):
        self.matches_today = 0


@dataclass
class AccountSwitchResult:
    """账号切换结果"""
    success: bool
    from_account: Optional[str] = None
    to_account: Optional[str] = None
    error_message: Optional[str] = None
    time_taken: float = 0.0
    host_gamertag: Optional[str] = None
    # True 表示主页 OCR 已匹配目标，未走 3/5/6 切档导航
    skipped_switch: bool = False


# 进 UT 主菜单前的场景链（对齐 streaming get_scenes_diagram）
FC_UT_LAUNCH_CHAIN: List[Tuple[int, int]] = [
    (1, 1),
    (2, 1),
    (203, 1),
    (101, 1),
    (126, 1),
]

FC_UT_TARGET_SCENES = {101, 126, 127, 147, 149}

# Xbox 主页（含 FC 磁贴），勿用场景 2/3（西瓜引导页误匹配）
XBOX_HOME_SCENES = {1, 24, 203}

# 系统 UI 场景易互相误匹配，校验时需取得最高置信度
XBOX_UI_AMBIGUOUS_SCENES = [1, 2, 3, 4, 5, 6, 7, 24, 203]

# 启动游戏/过场需较长等待才能出现目标场景
FC_TRANSITION_POST_WAIT: Dict[int, float] = {
    203: 60.0,
    101: 30.0,
    126: 20.0,
}

# 主页按 A 启动 FC：仍停留 203 时重试
FC_LAUNCH_203_MAX_ATTEMPTS = 3
FC_LAUNCH_203_RETRY_INTERVAL = 15.0
# 启动阶段 101 检测略放宽（过场/黑屏后 UI 未稳定）
FC_LAUNCH_101_THRESHOLD = 0.75

FC_LAUNCH_MANUAL_REASON = (
    "多次按 A 启动 FC 后仍停留在 Xbox 主页 (scene203)。"
    "请手工在主机上启动游戏并进入 UT 界面，完成后在平台点击「恢复任务」继续自动化。"
)

# Xbox「您是谁」列表向下扫描安全上限（正常触底以绿框 Y 不变为准）
DEFAULT_SCENE6_MAX_DOWN_STEPS = 50
DEFAULT_SCENE6_FOCUS_UNCHANGED_THRESHOLD = 2
DEFAULT_HOME_OCR_MAX_ATTEMPTS = 3
DEFAULT_HOME_OCR_RETRY_INTERVAL_SEC = 1.5
# 兼容旧常量名
MAX_PROFILE_LIST_SLOTS = DEFAULT_SCENE6_MAX_DOWN_STEPS

# 主页门禁 OCR 前：从 FC 磁贴焦点导航至档案头像（十字键一步一 OCR）
HOME_PROFILE_FOCUS_NAV_SEQUENCE = ("DPAD_UP", "DPAD_LEFT")
HOME_PROFILE_FOCUS_EXPLORE_SEQUENCE = ("DPAD_UP", "DPAD_LEFT", "DPAD_UP", "DPAD_LEFT")

# 账号门禁完成后进 FC：从头像获焦导航至 FC 磁贴（典型为十字键下）
HOME_PROFILE_TO_FC_NAV_SEQUENCE = ("DPAD_DOWN",)
# 探索序列含多次 DPAD_DOWN，在可滚动主页上易滚到底部「返回顶部」；优先 Guide→主页
HOME_FC_FOCUS_EXPLORE_SEQUENCE = (
    "DPAD_RIGHT",
    "DPAD_LEFT",
)


class ManualInterventionRequired(Exception):
    """需要人工处理后恢复自动化（任务应暂停而非终止）。"""

    def __init__(
        self,
        reason: str = FC_LAUNCH_MANUAL_REASON,
        *,
        scene_id: int = 203,
        error_code: str = "FC_LAUNCH_MANUAL_REQUIRED",
    ):
        super().__init__(reason)
        self.reason = reason
        self.scene_id = scene_id
        self.error_code = error_code


class AccountSwitcher:
    """
    游戏账号切换器（gamertag OCR + 场景校验）

    Step4 标准入口：ensure_target_game_account — 先 Xbox 主页，再 OCR 比对，按需切档。
    已有档案：引导菜单 → 场景3 → 场景5 → 场景6 → OCR 按 gamertag 选账号
    新用户：引导菜单 → 场景3 → 场景5 → 添加新用户 → 场景10+ 登录
    """

    def __init__(self):
        self.logger = get_logger('account_switcher')
        self._accounts: Dict[str, GameAccount] = {}
        self._current_account_id: Optional[str] = None
        self._action_executor = None
        self._scene_detector = None
        self._frame_getter: Optional[Callable[[], Awaitable[Any]]] = None
        self._stream_session = None
        self._reconnect_callback: Optional[Callable[[], Awaitable[bool]]] = None
        self._profile_bound_callback: Optional[
            Callable[[str, Optional[str]], Awaitable[None]]
        ] = None
        self._input_gate = None

    def set_input_gate(self, gate) -> None:
        """绑定输入闸门（task 级），用于在任务暂停时屏蔽手柄信号。"""
        self._input_gate = gate

    def set_accounts(self, accounts: List[Dict[str, Any]]) -> None:
        """加载游戏账号列表（替换现有账号集合）。"""
        self._accounts.clear()
        for idx, acc_data in enumerate(accounts):
            account = GameAccount(
                account_id=acc_data.get('account_id', ''),
                gamertag=acc_data.get('gamertag', ''),
                email=acc_data.get('email'),
                password=acc_data.get('password'),
                xuid=acc_data.get('xuid'),
                position_index=idx,
                is_new_user=bool(acc_data.get('is_new_user', False)),
                host_display_name=acc_data.get('host_display_name'),
                max_matches_per_day=acc_data.get('max_matches_per_day', 3),
            )
            self._accounts[account.account_id] = account

        self.logger.info(f"已加载 {len(self._accounts)} 个游戏账号")
        for acc in self._accounts.values():
            kind = "新用户" if acc.is_new_user else "已有账号"
            self.logger.info(f"  - {acc.gamertag} ({kind})")

    def set_action_executor(self, executor):
        self._action_executor = executor
        self.logger.info("账号切换器已绑定动作执行器")

    def set_scene_detector(self, detector):
        self._scene_detector = detector
        self.logger.info("账号切换器已绑定场景检测器")

    def set_frame_getter(self, getter: Callable[[], Awaitable[Any]]):
        """设置异步截帧函数，用于场景校验"""
        self._frame_getter = getter

    def set_stream_session(self, session):
        self._stream_session = session
        self.logger.info("账号切换器已绑定串流会话（保活）")

    def set_reconnect_callback(self, callback: Callable[[], Awaitable[bool]]):
        """设置 input 通道关闭时的重连回调（LAN SmartGlass 重握手）。"""
        self._reconnect_callback = callback
        self.logger.info("账号切换器已绑定输入通道重连回调")

    def set_task_context(self, context: Any):
        """绑定任务上下文，用于重连后清除 input dirty 标记。"""
        self._task_context = context

    def _trace_task_id(self) -> Optional[str]:
        ctx = getattr(self, "_task_context", None)
        if ctx is None:
            return None
        return getattr(ctx, "task_id", None) or getattr(ctx, "taskId", None)

    async def _capture_detected_scene(
        self,
        scene_id: int,
        image: Any,
        confidence: Optional[float] = None,
        *,
        note: str = "",
    ) -> None:
        """场景识别命中时按序号保存截图。"""
        try:
            from configs.scene_schemas import SCENE_NAMES
        except ImportError:
            SCENE_NAMES = {}
        label = SCENE_NAMES.get(int(scene_id), f"scene{scene_id}")
        session = get_scene_capture_session(self._trace_task_id())
        session.capture_frame(
            image,
            scene_id=int(scene_id),
            scene_label=label,
            confidence=confidence,
            note=note,
        )

    async def capture_automation_entry_snapshot(self) -> None:
        """Step4/切换开始前保存首帧并扫描模板场景置信度。"""
        from ..vision.template_manager import STEP4_REQUIRED_SCENE_IDS

        extra = [2, 3, 5, 6, 10, 203, 1, 24]
        scene_ids = sorted(set(STEP4_REQUIRED_SCENE_IDS + extra))
        await capture_entry_scene_survey(
            task_id=self._trace_task_id(),
            frame_getter=self._frame_getter,
            scene_detector=self._scene_detector,
            scene_ids=scene_ids,
        )

    def _stream_keepalive_loop(self, interval: float = 8.0):
        from ..xbox.stream_keepalive import StreamKeepaliveLoop

        return StreamKeepaliveLoop(
            lambda: self._stream_session,
            interval=interval,
            context=getattr(self, "_task_context", None),
        )

    def set_gamertag_sync_callback(
        self,
        callback: Optional[Callable[[str, Optional[str]], Awaitable[None]]],
    ) -> None:
        """切换/登录成功后可选回写主机 Gamertag 到平台 gameName。"""
        self._profile_bound_callback = callback

    async def _sync_host_gamertag(
        self,
        account: GameAccount,
        *,
        host_gamertag: Optional[str] = None,
    ) -> None:
        """同步 OCR 到的主机显示名到本地 host_display_name，并可选回写平台 gameName。"""
        resolved_name = (host_gamertag or "").strip() or None
        if resolved_name:
            account.host_display_name = resolved_name
        if not self._profile_bound_callback or not resolved_name:
            return
        try:
            await self._profile_bound_callback(account.account_id, resolved_name)
        except Exception as exc:
            self.logger.warning("主机 Gamertag 平台回写失败: %s", exc)

    @property
    def current_account(self) -> Optional[GameAccount]:
        if self._current_account_id:
            return self._accounts.get(self._current_account_id)
        return None

    @property
    def available_accounts(self) -> List[GameAccount]:
        return [acc for acc in self._accounts.values() if acc.is_available()]

    def get_account(self, account_id: str) -> Optional[GameAccount]:
        return self._accounts.get(account_id)

    async def prepare_without_switch(self, target_account_id: str) -> AccountSwitchResult:
        """
        跳过 Xbox 引导/档案切换（step4.skip_account_switch），假定当前主机档案已正确。

        仅确保 input 通道可用并标记当前游戏账号，后续由 launch_fc_to_ut_menu 接管。
        """
        start_time = time.time()
        from_account = self._current_account_id
        target_account = self._accounts.get(target_account_id)
        if not target_account:
            return AccountSwitchResult(
                success=False,
                from_account=from_account,
                error_message=f"账号不存在: {target_account_id}",
                time_taken=time.time() - start_time,
            )

        self.logger.info(
            "跳过账号切换，直接进入 FC/UT 流程 (%s)",
            target_account.gamertag,
        )
        if not await self._ensure_input_ready():
            return AccountSwitchResult(
                success=False,
                from_account=from_account,
                to_account=target_account_id,
                error_message="input DataChannel 不可用，无法继续自动化",
                time_taken=time.time() - start_time,
            )

        self._current_account_id = target_account_id
        target_account.mark_login()
        time_taken = time.time() - start_time
        return AccountSwitchResult(
            success=True,
            from_account=from_account,
            to_account=target_account_id,
            time_taken=time_taken,
        )

    async def ensure_target_game_account(
        self, target_account_id: str
    ) -> AccountSwitchResult:
        """
        Step4 账号门禁（分步固化流程）。

        1. 回到 Xbox 主页 (203/1/24)
        2. **先 OCR**（不论 FC 磁贴/头像是否获焦；裁剪区待截图标定）
        3. OCR 与目标游戏账号 **匹配** → 进 FC 分支（磁贴获焦，launch_fc 按 A）
        4. OCR **不匹配** → 切换账号分支（场景 3/5/6…，本阶段不按 A 进 FC）

        注意：串流账号邮箱仅用于 Step1 连主机，主页档案以 OCR 游戏账号为准。
        """
        start_time = time.time()
        from_account = self._current_account_id

        if target_account_id == from_account:
            return AccountSwitchResult(
                success=True,
                from_account=from_account,
                to_account=target_account_id,
                skipped_switch=True,
                time_taken=time.time() - start_time,
            )

        target_account = self._accounts.get(target_account_id)
        if not target_account:
            return AccountSwitchResult(
                success=False,
                from_account=from_account,
                error_message=f"账号不存在: {target_account_id}",
                time_taken=time.time() - start_time,
            )

        self.logger.info(
            "账号门禁: 目标游戏账号 %s (%s)",
            target_account.gamertag,
            target_account_id,
        )

        try:
            async with self._stream_keepalive_loop():
                if not await self._ensure_input_ready():
                    return AccountSwitchResult(
                        success=False,
                        from_account=from_account,
                        to_account=target_account_id,
                        error_message="input DataChannel 不可用，无法切换账号",
                        time_taken=time.time() - start_time,
                    )

                await self.capture_automation_entry_snapshot()

                if not await self._ensure_xbox_home_before_account_switch():
                    raise RuntimeError(
                        "账号门禁：未能回到 Xbox 主页（场景203/1/24）；"
                        "请手动关闭 FC/弹窗回到主页后重试"
                    )

                self.logger.info(
                    "账号门禁：先 OCR 比对（不依赖磁贴/头像焦点，裁剪区见 profile_name_reader HOME203_*）"
                )
                await self._log_home_profile_gate(target_account)

                if await self._is_already_signed_in_as(target_account):
                    self._current_account_id = target_account_id
                    target_account.mark_login()
                    self.logger.info(
                        "账号门禁：OCR 匹配 → 进 FC 分支（准备磁贴获焦）"
                    )
                    await self._prepare_home_for_fc_launch()
                    time_taken = time.time() - start_time
                    self.logger.info(
                        "账号门禁：主页已是目标 %s，跳过切档 (耗时: %.2fs)",
                        target_account.gamertag,
                        time_taken,
                    )
                    return AccountSwitchResult(
                        success=True,
                        from_account=from_account,
                        to_account=target_account_id,
                        skipped_switch=True,
                        time_taken=time_taken,
                    )

                self.logger.info(
                    "账号门禁：OCR 不匹配目标 %s → 切换账号分支（场景 3/5/6）",
                    target_account.gamertag,
                )
                await self._perform_full_account_switch(target_account)

            self._current_account_id = target_account_id
            target_account.mark_login()
            # 切档完成后由 launch_fc_to_ut_menu 进入 FC 分支（不在此处按 A）

            time_taken = time.time() - start_time
            self.logger.info(
                "账号门禁：切档完成 %s (耗时: %.2fs)",
                target_account_id,
                time_taken,
            )
            return AccountSwitchResult(
                success=True,
                from_account=from_account,
                to_account=target_account_id,
                skipped_switch=False,
                time_taken=time_taken,
            )

        except NotImplementedError as e:
            return AccountSwitchResult(
                success=False,
                from_account=from_account,
                to_account=target_account_id,
                error_message=str(e),
                time_taken=time.time() - start_time,
            )
        except Exception as e:
            self.logger.error(f"账号门禁失败: {e}")
            return AccountSwitchResult(
                success=False,
                from_account=from_account,
                to_account=target_account_id,
                error_message=str(e),
                time_taken=time.time() - start_time,
            )

    async def switch_to(self, target_account_id: str) -> AccountSwitchResult:
        """切换至目标游戏账号；实现为 ensure_target_game_account 别名。"""
        return await self.ensure_target_game_account(target_account_id)

    async def _log_home_focus_ocr_step(self, step_label: str) -> None:
        """主页门禁导航：每步十字键后 OCR + 焦点探针，便于调试图与坐标。"""
        norm = await self._get_normalized_frame()
        if norm is None:
            self.logger.info("主页焦点 OCR [%s]: 无法截帧", step_label)
            return

        from ..vision.profile_name_reader import (
            read_home_focus_state,
            read_home_profile_identity,
        )

        identity = read_home_profile_identity(norm)
        focus = read_home_focus_state(norm)
        self.logger.info(
            "主页焦点 OCR [%s]: name=%r email=%r profile_focus=%s fc_focus=%s "
            "settings_focus=%s back_to_top=%s "
            "probes=(avatar=%.3f fc=%.3f settings=%.3f btt=%.3f)",
            step_label,
            identity.display_name,
            identity.email_text,
            focus.get("profile_focused"),
            focus.get("fc_focused"),
            focus.get("settings_focused"),
            focus.get("back_to_top_focused"),
            focus.get("profile_ratio", 0.0),
            focus.get("fc_ratio", 0.0),
            focus.get("settings_ratio", 0.0),
            focus.get("back_to_top_ratio", 0.0),
        )

    async def _ensure_profile_avatar_focused_for_ocr(self) -> bool:
        """
        将焦点从 FC 磁贴移至左上角档案头像（十字键上 → 左）。

        当前门禁流程 **先 OCR 不调用本方法**；保留供后续切换账号分支细化时使用。
        """
        if not await self._is_on_xbox_home():
            self.logger.debug("非 Xbox 主页，跳过档案头像焦点导航")
            return False

        if await self._is_profile_avatar_focused():
            await self._log_home_focus_ocr_step("profile_already_focused")
            return True

        self.logger.info(
            "主页门禁：先将焦点移至档案头像（当前 FC磁贴=%s 设置=%s）",
            await self._is_fc_tile_focused(),
            await self._is_top_settings_focused(),
        )
        await self._log_home_focus_ocr_step("before_nav")

        for label, moves in (
            ("preset", HOME_PROFILE_FOCUS_NAV_SEQUENCE),
            ("explore", HOME_PROFILE_FOCUS_EXPLORE_SEQUENCE),
        ):
            for move in moves:
                if await self._is_profile_avatar_focused():
                    self.logger.info("档案头像已获焦（导航前已到位）")
                    return True
                await self._press_button(move, duration=0.1)
                await asyncio.sleep(0.35)
                await self._log_home_focus_ocr_step(f"{label}_{move}")
                if await self._is_profile_avatar_focused():
                    self.logger.info(
                        "档案头像已获焦（%s %s 后）", label, move
                    )
                    return True

        self.logger.warning(
            "未能将焦点移至档案头像，仍继续主页 OCR（请检查绿框探针坐标）"
        )
        return False

    async def _activate_back_to_top_if_focused(self) -> bool:
        """
        主页滚到底时焦点常在「返回顶部」；按 A 后页面回顶且绿框落在 FC 磁贴。

        返回 True 表示 FC 磁贴已获焦，可继续 launch_fc。
        """
        norm = await self._get_normalized_frame()
        if norm is None:
            return False
        from ..vision.profile_name_reader import is_home_back_to_top_focused

        if not is_home_back_to_top_focused(norm):
            return False

        self.logger.info(
            "检测到「返回顶部」获焦，按 A 滚回顶部（预期 FC 磁贴获焦）"
        )
        await self._press_button("A", duration=0.1)
        await asyncio.sleep(1.0)
        if await self._is_fc_tile_focused():
            self.logger.info("返回顶部触发后 FC 磁贴已获焦")
            return True
        self.logger.warning("返回顶部触发后 FC 磁贴仍未获焦")
        return False

    async def _return_home_via_guide_for_fc_tile(self) -> bool:
        """
        Guide(NEXUS) → 引导页选「主页」→ 回 Xbox 主页。

        系统默认会将绿框落在 FC 游戏磁贴上（比盲目十字键下滚到底更可靠）。
        对应 scene_transitions 场景2 transition_id=1 → 场景203。
        """
        if await self._is_fc_tile_focused():
            return True

        self.logger.info(
            "Guide → 主页：尝试回到 Xbox 主页（预期默认选中 FC 磁贴）"
        )
        await self._press_guide_button()
        if not await self._wait_for_guide(timeout=5.0):
            self.logger.warning("Guide 未打开引导页 (scene2)")
            await self._press_button("B", duration=0.08)
            await asyncio.sleep(0.3)
            return False

        ok = await self._run_scene_transition(2, 1)
        await asyncio.sleep(0.8)
        if not ok and not await self._is_on_xbox_home():
            self.logger.warning("Guide→主页 转移未确认 (2→203)")
            await self._press_button("B", duration=0.08)
            await asyncio.sleep(0.3)
            return False

        if await self._is_fc_tile_focused():
            self.logger.info("Guide→主页后 FC 磁贴已获焦")
            return True

        if await self._is_on_xbox_home():
            self.logger.warning(
                "Guide→主页成功但 FC 磁贴探针未确认，请检查 HOME203_FC_FOCUS_*"
            )
        return False

    async def _ensure_fc_tile_focused_for_launch(self) -> bool:
        """
        进 FC 分支：将焦点从头像/顶栏移至 FC 磁贴绿框。

        典型路径（头像已获焦）：十字键下 → FC 磁贴高亮；每步 OCR+焦点探针。
        仅在 launch_fc / 按 A 启动前调用，账号切档流程中禁止按 A 进 FC。
        """
        if not await self._is_on_xbox_home():
            self.logger.debug("非 Xbox 主页，跳过 FC 磁贴焦点导航")
            return False

        if await self._is_fc_tile_focused():
            await self._log_home_focus_ocr_step("fc_tile_already_focused")
            return True

        if await self._activate_back_to_top_if_focused():
            return True

        if await self._return_home_via_guide_for_fc_tile():
            return True

        self.logger.info(
            "进 FC 前：将焦点移至 FC 磁贴（profile_focus=%s）",
            await self._is_profile_avatar_focused(),
        )
        await self._log_home_focus_ocr_step("before_fc_nav")

        for label, moves in (
            ("preset", HOME_PROFILE_TO_FC_NAV_SEQUENCE),
            ("explore", HOME_FC_FOCUS_EXPLORE_SEQUENCE),
        ):
            for move in moves:
                if await self._is_fc_tile_focused():
                    return True
                await self._press_button(move, duration=0.1)
                await asyncio.sleep(0.35)
                await self._log_home_focus_ocr_step(f"fc_{label}_{move}")
                if await self._is_fc_tile_focused():
                    self.logger.info("FC 磁贴已获焦（%s %s 后）", label, move)
                    return True
                if await self._activate_back_to_top_if_focused():
                    return True

        if await self._activate_back_to_top_if_focused():
            return True

        if await self._return_home_via_guide_for_fc_tile():
            return True

        self.logger.warning("未能将焦点移至 FC 磁贴")
        return False

    async def _prepare_home_for_fc_launch(self) -> None:
        """
        账号门禁/切档完成后：确认在主页且 FC 磁贴获焦，供 launch_fc 按 A 启动。

        与账号分支对称：账号 OCR/切档在头像获焦；进 FC 在磁贴获焦后按 A。
        """
        if not await self._is_on_xbox_home():
            self.logger.info("账号门禁后不在主页，尝试 B/Guide 退回")
            if not await self._ensure_xbox_home_before_account_switch(timeout=30.0):
                self.logger.warning("账号门禁后未能回到 Xbox 主页，进 FC 可能失败")
                return

        if await self._is_fc_tile_focused():
            self.logger.info("账号门禁后 FC 磁贴已获焦，可直接 launch_fc")
            return

        if await self._ensure_fc_tile_focused_for_launch():
            return

        self.logger.info("FC 磁贴预设导航未成功，回退通用磁贴导航")
        await self._navigate_to_fc_tile_on_home()

    async def _log_home_profile_gate(self, target_account: GameAccount) -> None:
        """主页门禁：当前帧 OCR + 焦点探针（仅日志，不移动焦点）。"""
        """主页门禁：记录当前主页档案与目标游戏账号（OCR，仅日志）。"""
        await self._log_home_focus_ocr_step(
            f"gate_ocr_{target_account.gamertag or 'unknown'}"
        )
        self.logger.info(
            "账号门禁：目标 gamertag=%s email=%s",
            target_account.gamertag,
            self._mask_email(target_account.email),
        )

    async def _perform_full_account_switch(self, target_account: GameAccount) -> None:
        """
        主页门禁未匹配时，走 Guide → 场景3/5/6 完整切档。

        进入前焦点应在档案头像（ensure_profile_avatar）；本流程不按 A 启动 FC。
        """
        if await self._wait_for_scene(3, timeout=2.0, strict=True):
            self.logger.info("已在场景3（档案和系统），跳过引导页")
        else:
            if not await self._is_on_xbox_home():
                self.logger.warning(
                    "未在场景3且不在 Xbox 主页，尝试打开引导页"
                )
            on_home = await self._detect_any_scene(
                list(XBOX_HOME_SCENES), strict=False
            )
            guide_ok = await self._open_guide_menu()
            if not guide_ok:
                self.logger.warning("未能打开引导页，尝试备用导航")
                if on_home in XBOX_HOME_SCENES or on_home is None:
                    if not await self._wait_for_scene(3, timeout=3.0):
                        await self._navigate_to_accounts_from_home()
                else:
                    await self._navigate_to_accounts_system()
            elif not await self._wait_for_scene(3, timeout=2.0):
                if not await self._run_scene_transition(2, 2):
                    self.logger.warning("场景转移 2->3 未确认，回退到手动导航")
                    await self._navigate_to_accounts_system()

        if not await self._wait_for_scene(3):
            await self._log_scene_probe([2, 3, 5])
            await self._save_debug_frame(3)
            raise RuntimeError("未进入档案和系统页面（场景3）")

        if target_account.is_new_user and target_account.needs_credential_login():
            from .scenes.add_account import AddAccountScene

            await AddAccountScene(self).run(target_account)
        else:
            if not await self._select_add_switch():
                raise RuntimeError("未进入添加和切换页面（场景5）")

            scene6_ok = await self._enter_account_selection()
            if not scene6_ok:
                if await self._is_already_signed_in_as(target_account):
                    self.logger.info(
                        "场景6未确认但主页已是目标账号 (%s)，跳过档案列表选择",
                        target_account.gamertag,
                    )
                elif await self._is_scene6_template_without_layout():
                    await self._save_debug_frame(6)
                    raise RuntimeError(
                        "场景6模板误匹配：当前帧不具备档案列表布局"
                    )
                else:
                    raise RuntimeError("未进入账号选择页面（场景6）")
            else:
                found_index = await self._select_account_by_gamertag(
                    target_account.gamertag,
                    email=target_account.email,
                    host_display_name=target_account.host_display_name,
                )
                if found_index is None:
                    self.logger.info(
                        "场景6列表扫尽未找到 %s，走添加账号",
                        target_account.gamertag,
                    )
                    from .scenes.add_account import AddAccountScene

                    await AddAccountScene(self).run(target_account)
                else:
                    target_account.position_index = found_index
                    await self._confirm_account_selection()

                    if await self._wait_for_scene(10, timeout=10.0):
                        if target_account.email and target_account.password:
                            self.logger.info(
                                "切换后出现登录页，使用凭据登录 (%s)",
                                target_account.gamertag,
                            )
                            await self._login_with_credentials(
                                target_account.email, target_account.password
                            )
                            host_tag = await self._read_host_gamertag_from_profile_list()
                            await self._sync_host_gamertag(
                                target_account, host_gamertag=host_tag
                            )
                        else:
                            raise RuntimeError(
                                f"档案 {target_account.gamertag} 需重新登录，"
                                "但未配置邮箱/密码凭据"
                            )
                    else:
                        self.logger.info(
                            "档案切换完成，未出现登录页 (%s)",
                            target_account.gamertag,
                        )
                        host_tag = await self._read_host_gamertag_from_profile_list()
                        await self._sync_host_gamertag(
                            target_account, host_gamertag=host_tag
                        )

        from ..core.config import config as app_config

        post_home_wait = float(
            app_config.get("step4.post_switch_home_wait_sec", 25.0)
        )
        if not await self._ensure_xbox_home_before_account_switch(
            timeout=post_home_wait
        ):
            self.logger.warning(
                "切档/添加完成后未能确认回到 Xbox 主页，交由 launch_fc 兜底"
            )

    async def run_add_account_flow(self, target_account: GameAccount) -> None:
        """
        添加新用户场景（scene5/6 → 添加新用户 → scene10 凭据登录）。

        供 is_new_user、scene6 列表扫尽等分支统一调用。
        """
        if not target_account.email or not target_account.password:
            raise RuntimeError(
                f"档案 {target_account.gamertag or target_account.account_id} "
                "需在主机添加，但未配置邮箱/密码凭据"
            )

        on_scene6 = await self._wait_for_scene6_confirmed(timeout=1.5, strict=False)
        if on_scene6:
            if not await self._ensure_scene6_add_new_user_focused():
                raise RuntimeError("未能定位「添加新用户」行")
            await self._press_button("A", duration=0.1)
            await asyncio.sleep(2.0)
        else:
            if not await self._select_add_switch():
                raise RuntimeError("未进入添加和切换页面（场景5）")
            if not await self._wait_for_scene(5, timeout=15.0):
                raise RuntimeError("未进入添加和切换页面（场景5）")
            await self._select_add_new_user()

        await self._login_with_credentials(
            target_account.email, target_account.password
        )
        host_tag = await self._read_host_gamertag_from_profile_list()
        await self._sync_host_gamertag(target_account, host_gamertag=host_tag)
        if host_tag:
            target_account.gamertag = host_tag
            target_account.host_display_name = host_tag

    async def launch_fc_to_ut_menu(self, timeout: float = 90.0) -> bool:
        """切换账号后从 Xbox 主页启动 FC 并进入 UT 相关界面。"""
        self.logger.info("开始启动 FC 并导航至 UT 界面")
        if not await self._ensure_input_ready():
            self.logger.error("进游戏前 input DataChannel 不可用，中止启动 FC")
            return False

        async with self._stream_keepalive_loop():
            return await self._launch_fc_to_ut_menu_inner(timeout)

    async def _launch_fc_to_ut_menu_inner(self, timeout: float) -> bool:
        await self._press_button('B', duration=0.08)
        await asyncio.sleep(0.4)

        current_ut = await self._detect_any_scene(
            list(FC_UT_TARGET_SCENES), strict=False
        )
        if current_ut in FC_UT_TARGET_SCENES:
            self.logger.info(f"已在游戏/UT 场景: {current_ut}")
            return True

        home_state = await self._detect_any_scene([203, 1, 24], strict=False)
        if home_state in XBOX_HOME_SCENES or home_state is None:
            if not await self._is_fc_tile_focused():
                await self._navigate_to_fc_tile_on_home()
            else:
                self.logger.info("203 主页 FC 磁贴已获焦，直接进入启动链")
            chain = [(203, 1), (101, 1), (126, 1)]
        elif home_state == 101:
            chain = [(101, 1), (126, 1)]
        elif home_state == 126:
            chain = [(126, 1)]
        else:
            await self._press_guide_button()
            if await self._wait_for_scene(2, timeout=6.0):
                await self._navigate_to_fc_tile_on_home()
                chain = [(203, 1), (101, 1), (126, 1)]
            else:
                chain = list(FC_UT_LAUNCH_CHAIN)

        for scene_id, transition_id in chain:
            if await self._detect_any_scene(list(FC_UT_TARGET_SCENES), strict=False):
                return True
            if scene_id == 203 and not await self._is_fc_tile_focused():
                self.logger.info("启动 FC 前再次确认磁贴焦点")
                await self._navigate_to_fc_tile_on_home()
            if not await self._recover_input_if_closed():
                self.logger.error(
                    f"FC 场景 {scene_id} 转移前 input 通道不可用，中止导航"
                )
                await self._save_debug_frame(scene_id)
                return False
            if scene_id == 203:
                ok = await self._launch_fc_from_home_tile()
            else:
                ok = await self._run_scene_transition(scene_id, transition_id)
            if not ok:
                self.logger.warning(
                    f"场景转移未确认: {scene_id} -> transition {transition_id}"
                )
                await self._save_debug_frame(scene_id)
            await asyncio.sleep(0.6)

        ut_ok = await self._wait_for_any_scene(list(FC_UT_TARGET_SCENES), timeout=timeout)
        if ut_ok:
            return True

        account = self.current_account
        ea_email = (account.email if account else None) or ""
        from .ea_onboarding import run_ea_onboarding

        self.logger.info(
            "FC 启动后未进入 UT，尝试 EA/FC 首登引导 (email=%s)",
            ea_email[:3] + "***" if ea_email else "(empty)",
        )
        guided = await run_ea_onboarding(
            self,
            ea_email=ea_email,
            timeout=min(max(timeout, 300.0), 900.0),
        )
        if guided:
            return True
        return False

    def _scene6_max_down_steps(self) -> int:
        from ..core.config import config as app_config

        return int(
            app_config.get(
                "step4.scene6_max_down_steps", DEFAULT_SCENE6_MAX_DOWN_STEPS
            )
        )

    def _scene6_focus_unchanged_threshold(self) -> int:
        from ..core.config import config as app_config

        return int(
            app_config.get(
                "step4.scene6_focus_unchanged_threshold",
                DEFAULT_SCENE6_FOCUS_UNCHANGED_THRESHOLD,
            )
        )

    def _home_profile_matches_target(
        self, identity: Any, target_account: GameAccount
    ) -> Tuple[bool, str]:
        """主页 OCR 结果是否与目标游戏账号一致（含短 gamertag 邮箱交叉确认）。"""
        from ..vision.profile_name_reader import (
            email_local_part,
            gamertag_matches,
            normalize_gamertag,
            profile_matches_game_account,
        )

        matched, reason = profile_matches_game_account(
            identity.display_name,
            target_account.gamertag,
            target_account.email,
            detected_email=identity.email_text,
            host_display_name=target_account.host_display_name,
            combined_text=identity.combined,
        )
        if matched and reason == "gamertag":
            if len(normalize_gamertag(target_account.gamertag)) < 4:
                email_ok = False
                if target_account.email:
                    local = email_local_part(target_account.email)
                    if identity.email_text and gamertag_matches(
                        identity.email_text, local
                    ):
                        email_ok = True
                    if (
                        identity.email_text
                        and target_account.email.strip().lower()
                        in identity.email_text.strip().lower()
                    ):
                        email_ok = True
                if not email_ok:
                    self.logger.info(
                        "短 gamertag 匹配但邮箱未交叉确认，仍执行账号切换"
                    )
                    matched = False
        return matched, reason

    async def _read_scene6_focus_y(self) -> Optional[int]:
        """场景6 当前绿框焦点行 Y 中心。"""
        frame = await self._frame_getter() if self._frame_getter else None
        if frame is None:
            return None
        image = _extract_frame_image(frame)
        if self._scene_detector and hasattr(self._scene_detector, "_normalize_frame"):
            image = self._scene_detector._normalize_frame(image, 6)
        from ..vision.profile_name_reader import get_scene6_focus_row_y

        return get_scene6_focus_row_y(image)

    async def _ensure_scene6_add_new_user_focused(self) -> bool:
        """将绿框移至「添加新用户」行（已在则直接返回）。"""
        from ..vision.profile_name_reader import is_scene6_add_new_user_row

        detected = await self._read_focused_gamertag_from_frame()
        if is_scene6_add_new_user_row(detected):
            return True
        return await self._scroll_scene6_to_add_new_user()

    async def _scroll_scene6_to_add_new_user(self) -> bool:
        """
        在场景6 列表中向下滚动，直到「添加新用户」获焦或绿框 Y 触底。
        """
        from ..vision.profile_name_reader import is_scene6_add_new_user_row

        unchanged_steps = 0
        threshold = self._scene6_focus_unchanged_threshold()
        max_steps = self._scene6_max_down_steps()
        prev_y = await self._read_scene6_focus_y()

        for step in range(max_steps):
            detected = await self._read_focused_gamertag_from_frame()
            if is_scene6_add_new_user_row(detected):
                self.logger.info("已定位「添加新用户」行（step=%s）", step)
                return True

            await self._press_button("DPAD_DOWN", duration=0.1)
            await asyncio.sleep(0.18)
            new_y = await self._read_scene6_focus_y()
            if new_y is not None and prev_y is not None and new_y == prev_y:
                unchanged_steps += 1
                if unchanged_steps >= threshold:
                    detected = await self._read_focused_gamertag_from_frame()
                    if is_scene6_add_new_user_row(detected):
                        return True
                    self.logger.warning(
                        "场景6 绿框触底但 OCR 未识别「添加新用户」"
                    )
                    return False
            else:
                unchanged_steps = 0
            prev_y = new_y

        return is_scene6_add_new_user_row(
            await self._read_focused_gamertag_from_frame()
        )

    async def _is_already_signed_in_as(self, target_account: GameAccount) -> bool:
        """
        主页左上角 OCR 显示名/邮箱，与 gamertag、host_display_name、邮箱本地段比对。

        匹配则跳过引导切换。左上角文案会轮播（仅 gamertag / gamertag+邮箱 / 多档案），
        故 **未命中也重试** 至 home_ocr_max_attempts，全部轮次均未命中才走切档。
        """
        from ..core.config import config as app_config
        from ..vision.profile_name_reader import read_home_profile_identity

        current_ut = await self._detect_any_scene(list(FC_UT_TARGET_SCENES), strict=False)
        if current_ut in FC_UT_TARGET_SCENES:
            return False

        max_attempts = int(
            app_config.get(
                "step4.home_ocr_max_attempts", DEFAULT_HOME_OCR_MAX_ATTEMPTS
            )
        )
        interval = float(
            app_config.get(
                "step4.home_ocr_retry_interval_sec",
                DEFAULT_HOME_OCR_RETRY_INTERVAL_SEC,
            )
        )

        last_identity = None
        last_norm = None
        for attempt in range(1, max_attempts + 1):
            norm = await self._get_normalized_frame()
            if norm is None:
                self.logger.debug(
                    "主页档案 OCR 第 %s/%s 次：无法截帧", attempt, max_attempts
                )
                if attempt < max_attempts:
                    await asyncio.sleep(interval)
                continue

            identity = read_home_profile_identity(norm)
            last_identity = identity
            last_norm = norm

            if not identity.display_name and not identity.email_text:
                self.logger.info(
                    "主页 OCR 第 %s/%s 次未读到档案，等待轮播",
                    attempt,
                    max_attempts,
                )
                if attempt < max_attempts:
                    await asyncio.sleep(interval)
                    continue
                break

            matched, reason = self._home_profile_matches_target(
                identity, target_account
            )
            if matched:
                on_home = await self._detect_any_scene([203, 1, 24], strict=False)
                home_like = on_home in XBOX_HOME_SCENES or await self._is_home_203_dominant()
                if home_like:
                    self.logger.info(
                        "主页 OCR 匹配目标 (name=%r, email=%r, by=%s, attempt=%s)，跳过账号切换",
                        identity.display_name,
                        identity.email_text,
                        reason,
                        attempt,
                    )
                else:
                    self.logger.info(
                        "主页 OCR 匹配目标 (name=%r, by=%s, scene=%s, attempt=%s)，跳过账号切换",
                        identity.display_name,
                        reason,
                        on_home,
                        attempt,
                    )
                return True

            self.logger.info(
                "主页 OCR 第 %s/%s 次未匹配目标 %s (name=%r email=%r)，等待轮播",
                attempt,
                max_attempts,
                target_account.gamertag,
                identity.display_name,
                identity.email_text,
            )
            if attempt < max_attempts:
                await asyncio.sleep(interval)

        if last_norm is not None and last_identity is not None:
            self.logger.info(
                "主页 OCR %s 次均未匹配目标 %s，继续账号切换流程",
                max_attempts,
                target_account.gamertag,
            )
            await self._save_home_ocr_debug(
                last_norm, last_identity, target_account.gamertag
            )
        elif last_identity is not None:
            on_home = await self._detect_any_scene([203, 1, 24], strict=False)
            self.logger.info(
                "主页左上角 OCR 未识别档案 (scene=%s)，继续账号切换流程",
                on_home,
            )
        return False

    async def _verify_scene6_layout(self) -> bool:
        """场景 6 除模板外，要求左侧档案列表布局（绿框或列表 OCR）。"""
        if not self._frame_getter:
            return False
        frame = await self._frame_getter()
        if frame is None:
            return False
        image = _extract_frame_image(frame)
        if self._scene_detector and hasattr(self._scene_detector, "_normalize_frame"):
            image = self._scene_detector._normalize_frame(image, 6)
        from ..vision.profile_name_reader import scene6_list_layout_present

        if scene6_list_layout_present(image):
            return True
        self.logger.warning("场景6模板命中但档案列表布局未确认")
        return False

    async def _is_scene6_template_without_layout(self, *, strict: bool = True) -> bool:
        """模板判为场景6但左侧无档案列表（如 FC 游戏详情页误匹配）。"""
        if await self._detect_any_scene([6], strict=strict) is None:
            return False
        return not await self._verify_scene6_layout()

    async def _wait_for_scene6_confirmed(
        self,
        timeout: float = 12.0,
        *,
        strict: bool = True,
    ) -> bool:
        """场景6须同时满足：模板命中 + 档案列表布局。"""
        if not self._scene_detector or not self._frame_getter:
            self.logger.warning("跳过场景6校验（未绑定检测器或截帧）")
            return True

        deadline = time.time() + timeout
        while time.time() < deadline:
            if await self._detect_any_scene([6], strict=strict) is not None:
                if await self._verify_scene6_layout():
                    self.logger.info("场景6校验通过（模板+布局）")
                    return True
                self.logger.debug("场景6模板命中但布局未确认，继续等待")
            await asyncio.sleep(0.5)

        self.logger.warning(f"场景6校验超时（模板+布局）({timeout}s)")
        await self._log_scene_probe([6])
        await self._save_debug_frame(6)
        return False

    async def _save_home_ocr_debug(
        self,
        norm_image: Any,
        identity: Any,
        gamertag: str,
    ) -> None:
        """主页 OCR 失败或不匹配时保存裁剪区域，便于调整坐标。"""
        try:
            import os
            import cv2
            from ..vision.profile_name_reader import (
                HOME203_EMAIL_BOTTOM,
                HOME203_EMAIL_LEFT,
                HOME203_EMAIL_RIGHT,
                HOME203_EMAIL_TOP,
                HOME203_NAME_BOTTOM,
                HOME203_NAME_LEFT,
                HOME203_NAME_RIGHT,
                HOME203_NAME_TOP,
            )

            log_dir = get_logs_dir_fallback()
            os.makedirs(log_dir, exist_ok=True)
            stamp = int(time.time())
            safe_tag = re.sub(r"[^a-zA-Z0-9_-]", "_", gamertag or "unknown")[:32]

            def _save_crop(left, top, right, bottom, suffix: str) -> None:
                h, w = norm_image.shape[:2]
                sx, sy = w / 960.0, h / 540.0
                x1, x2 = int(left * sx), min(w, int(right * sx))
                y1, y2 = int(top * sy), min(h, int(bottom * sy))
                if x2 <= x1 or y2 <= y1:
                    return
                path = os.path.join(
                    log_dir, f"debug_home_ocr_{suffix}_{safe_tag}_{stamp}.png"
                )
                cv2.imwrite(path, norm_image[y1:y2, x1:x2])

            _save_crop(
                HOME203_NAME_LEFT,
                HOME203_NAME_TOP,
                HOME203_NAME_RIGHT,
                HOME203_NAME_BOTTOM,
                "name",
            )
            _save_crop(
                HOME203_EMAIL_LEFT,
                HOME203_EMAIL_TOP,
                HOME203_EMAIL_RIGHT,
                HOME203_EMAIL_BOTTOM,
                "email",
            )

            overlay = norm_image.copy()
            h, w = overlay.shape[:2]
            sx, sy = w / 960.0, h / 540.0

            def _draw_box(left, top, right, bottom, color, label):
                x1, x2 = int(left * sx), int(right * sx)
                y1, y2 = int(top * sy), int(bottom * sy)
                cv2.rectangle(overlay, (x1, y1), (x2, y2), color, 2)
                cv2.putText(
                    overlay, label, (x1, max(12, y1 - 4)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1, cv2.LINE_AA,
                )

            _draw_box(
                HOME203_NAME_LEFT, HOME203_NAME_TOP,
                HOME203_NAME_RIGHT, HOME203_NAME_BOTTOM,
                (0, 0, 255), "NAME",
            )
            _draw_box(
                HOME203_EMAIL_LEFT, HOME203_EMAIL_TOP,
                HOME203_EMAIL_RIGHT, HOME203_EMAIL_BOTTOM,
                (255, 128, 0), "EMAIL",
            )
            overlay_path = os.path.join(
                log_dir, f"debug_home_ocr_overlay_{safe_tag}_{stamp}.png"
            )
            cv2.imwrite(overlay_path, overlay)

            self.logger.warning(
                "主页 OCR debug 已保存: name=%r email=%r -> %s/debug_home_ocr_*_%s.png "
                "overlay=%s",
                getattr(identity, "display_name", ""),
                getattr(identity, "email_text", ""),
                os.path.abspath(log_dir),
                stamp,
                os.path.abspath(overlay_path),
            )
        except Exception as exc:
            self.logger.debug("保存主页 OCR debug 失败: %s", exc)

    @staticmethod
    def _mask_email(email: Optional[str]) -> str:
        if not email or "@" not in email:
            return "(empty)"
        local, domain = email.split("@", 1)
        if len(local) <= 2:
            return f"{local[0]}***@{domain}"
        return f"{local[:2]}***@{domain}"

    async def _navigate_to_fc_tile_on_home(self):
        """从 Xbox 主页移焦到 FC 游戏磁贴（进 FC 分支，磁贴获焦后才按 A）。"""
        if await self._is_fc_tile_focused():
            self.logger.info("FC 磁贴已获焦，跳过磁贴导航")
            return

        if await self._activate_back_to_top_if_focused():
            return

        if await self._return_home_via_guide_for_fc_tile():
            return

        if await self._is_profile_avatar_focused():
            self.logger.info("从头像获焦导航至 FC 磁贴（十字键下）")
            if await self._ensure_fc_tile_focused_for_launch():
                return

        self.logger.info("导航至 FC 游戏磁贴（离开顶栏设置焦点）")
        for _ in range(4):
            await self._press_button('B', duration=0.08)
            await asyncio.sleep(0.3)
        if await self._is_top_settings_focused():
            self.logger.info("顶栏「设置」仍获焦，追加 B 退出")
            for _ in range(2):
                await self._press_button('B', duration=0.08)
                await asyncio.sleep(0.25)

        if await self._return_home_via_guide_for_fc_tile():
            return

        # 从头像区单次下移至 FC；避免多次 DOWN 滚到页面底部
        if await self._is_profile_avatar_focused() or await self._is_on_xbox_home():
            await self._press_button('DPAD_DOWN', duration=0.1)
            await asyncio.sleep(0.35)
            if await self._is_fc_tile_focused():
                self.logger.info("FC 磁贴绿框焦点已确认（单次 DPAD_DOWN）")
                return
            if await self._activate_back_to_top_if_focused():
                return

        if await self._detect_any_scene([203], strict=False) == 203:
            self.logger.info("scene203 校验通过（FC 磁贴可见）")
        else:
            self.logger.warning("FC 磁贴焦点未确认 (scene203)，仍尝试启动游戏")

    async def _is_on_xbox_home(self) -> bool:
        """当前帧是否为 Xbox 主机主页（203/1/24 或 scene203 高置信）。"""
        home = await self._detect_any_scene(list(XBOX_HOME_SCENES), strict=False)
        on_home = home in XBOX_HOME_SCENES or await self._is_home_203_dominant()
        if not on_home:
            return False

        # 设置/档案页常误匹配 scene 24；账号 UI 模板置信更高时先 B 退回真主页
        if self._scene_detector and self._frame_getter:
            frame = await self._frame_getter()
            image = _extract_frame_image(frame) if frame else None
            if image is not None:
                home_best = 0.0
                account_best = 0.0
                for scene_id in XBOX_HOME_SCENES:
                    result = self._scene_detector.recognize_scene(
                        image,
                        scene_id=scene_id,
                        threshold=self._scene_match_threshold(scene_id),
                    )
                    home_best = max(home_best, result.confidence)
                for scene_id in (3, 4, 5, 6):
                    result = self._scene_detector.recognize_scene(
                        image,
                        scene_id=scene_id,
                        threshold=self._scene_match_threshold(scene_id),
                    )
                    account_best = max(account_best, result.confidence)
                if account_best >= 0.75 and account_best > home_best + 0.05:
                    self.logger.debug(
                        "账号 UI 置信度高于主页模板 (account=%.3f home=%.3f)，"
                        "不视为 Xbox 主页",
                        account_best,
                        home_best,
                    )
                    return False
        return True

    async def _ensure_xbox_home_before_account_switch(
        self,
        timeout: float = 45.0,
    ) -> bool:
        """
        账号切换前强制落在 Xbox 主页 (203/1/24)。

        若停在 FC 游戏 Hub、详情页、多主机冲突弹窗等，仅用 B/Guide 退回，不盲按 A。
        """
        if await self._is_on_xbox_home():
            home = await self._detect_any_scene(list(XBOX_HOME_SCENES), strict=False)
            self.logger.info(
                "账号切换前已在 Xbox 主页 (scene=%s)",
                home if home in XBOX_HOME_SCENES else 203,
            )
            return True

        self.logger.warning(
            "账号切换前未在 Xbox 主页 (203/1/24)，尝试 B/Guide 退回 (timeout=%ss)",
            timeout,
        )
        deadline = time.time() + timeout
        step = 0
        while time.time() < deadline:
            if await self._is_on_xbox_home():
                home = await self._detect_any_scene(list(XBOX_HOME_SCENES), strict=False)
                self.logger.info(
                    "已回到 Xbox 主页 (scene=%s)",
                    home if home in XBOX_HOME_SCENES else 203,
                )
                return True

            step += 1
            if step == 1 or step % 6 == 0:
                await self._press_guide_button()
            else:
                await self._press_button("B", duration=0.1)
            await asyncio.sleep(0.45)
            if step % 5 == 0:
                await self._recover_input_if_closed()
                await self._send_keepalive()

        self.logger.warning("账号切换前未能回到 Xbox 主页")
        await self._log_scene_probe([203, 1, 24, 3, 5, 6])
        await self._save_debug_frame(203)
        return False

    async def _is_home_203_dominant(self) -> bool:
        """当前帧是否仍为 Xbox 主页 scene203（高置信度）。"""
        if not self._scene_detector or not self._frame_getter:
            return False
        frame = await self._frame_getter()
        if frame is None:
            return False
        image = _extract_frame_image(frame)
        threshold = self._scene_match_threshold(203)
        result = self._scene_detector.recognize_scene(
            image, scene_id=203, threshold=threshold
        )
        return bool(result.matched)

    async def _wait_for_game_launch_progress(self, timeout: float) -> bool:
        """
        等待游戏启动进展：进入 UT 相关场景，或已离开 Xbox 主页 203。
        """
        deadline = time.time() + timeout
        last_log = 0.0
        while time.time() < deadline:
            ut = await self._detect_any_scene(list(FC_UT_TARGET_SCENES), strict=False)
            if ut in FC_UT_TARGET_SCENES:
                self.logger.info(f"游戏/UT 场景就绪: {ut}")
                return True
            if not await self._is_home_203_dominant():
                self.logger.info("已离开 Xbox 主页 (203)，判定游戏加载中")
                return True
            now = time.time()
            if now - last_log >= 10.0:
                self.logger.info("等待 FC 启动：仍停留在 Xbox 主页 203...")
                last_log = now
            if not await self._recover_input_if_closed():
                self.logger.warning("等待 FC 启动时 input 通道不可用")
            else:
                await self._send_keepalive()
            await asyncio.sleep(0.5)
        return False

    async def exit_fc_to_xbox_home(self, timeout: float = 90.0) -> bool:
        """
        从 FC/UT 退出回到 Xbox 主机主页，便于切换下一游戏账号。

        策略：轮询 scene 203/1/24；未在主页则 B 回退，周期性 Guide+B 尝试关闭游戏/ overlay。
        不保证一次成功，超时返回 False，由调用方决定是否继续 switch_to。
        """
        self.logger.info("退出 FC/UT，返回 Xbox 主页 (timeout=%ss)", timeout)
        async with self._stream_keepalive_loop():
            if not await self._ensure_input_ready():
                self.logger.error("exit_fc_to_xbox_home: input 通道不可用")
                return False

            deadline = time.time() + timeout
            step = 0
            while time.time() < deadline:
                home = await self._detect_any_scene([203, 1, 24], strict=False)
                if home in XBOX_HOME_SCENES:
                    self.logger.info("已回到 Xbox 主页 scene=%s", home)
                    return True
                if await self._is_home_203_dominant():
                    self.logger.info("已回到 Xbox 主页 (scene203 高置信)")
                    return True

                step += 1
                if step % 14 == 0:
                    await self._press_guide_button()
                    await asyncio.sleep(0.5)
                    for _ in range(3):
                        await self._press_button("B", duration=0.1)
                        await asyncio.sleep(0.35)
                else:
                    await self._press_button("B", duration=0.1)
                    await asyncio.sleep(0.45)

                if step % 6 == 0:
                    await self._recover_input_if_closed()
                    await self._send_keepalive()

            self.logger.warning("exit_fc_to_xbox_home 超时，未确认回到 Xbox 主页")
            await self._save_debug_frame(203)
            return False

    async def dismiss_until_scenes(
        self,
        target_scene_ids: List[int],
        timeout: float = 60.0,
        *,
        label: str = "",
        probe_scene_ids: Optional[List[int]] = None,
    ) -> bool:
        """
        轮询识别当前 scene，直到命中 target_scene_ids 或超时。

        每轮 (~1Hz)：
        - 已在目标 scene → 成功返回
        - 当前 scene 在 SCENE_TRANSITIONS 有配置 → 执行首选转移
        - 已识别 scene 但无转移表 → 按 A（过场 scene 长按，普通弹窗短按）
        - 模板均未匹配 → 特定 label（如 SQB-PREMATCH）周期性尝试长按 A
        """
        from configs.scene_transitions import (
            DISMISS_HOLD_A_UNMATCHED_LABELS,
            get_transitions_by_scene,
            resolve_automation_a_press_sec,
        )

        if not target_scene_ids:
            return True

        tag = f"[{label}] " if label else ""
        targets = set(target_scene_ids)
        probes = list(
            dict.fromkeys(
                (probe_scene_ids or []) + list(target_scene_ids)
            )
        )
        self.logger.info(
            "%sdismiss_until_scenes 目标=%s probes=%s timeout=%ss",
            tag,
            sorted(targets),
            len(probes),
            timeout,
        )

        async with self._stream_keepalive_loop():
            if not await self._ensure_input_ready():
                self.logger.error("%sdismiss_until_scenes: input 不可用", tag)
                return False

            deadline = time.time() + timeout
            step = 0
            while time.time() < deadline:
                hit = await self._detect_any_scene(
                    list(target_scene_ids), strict=False
                )
                if hit in targets:
                    self.logger.info("%s已到达目标 scene %s", tag, hit)
                    return True

                current = None
                if probes:
                    current = await self._detect_any_scene(probes, strict=False)

                if current is not None:
                    transitions = get_transitions_by_scene(current)
                    if transitions:
                        tid = transitions[0]["transition_id"]
                        self.logger.info(
                            "%s当前 scene=%s，执行转移 %s/%s",
                            tag,
                            current,
                            current,
                            tid,
                        )
                        await self._run_scene_transition(current, tid)
                    else:
                        duration = resolve_automation_a_press_sec(current)
                        self.logger.debug(
                            "%s当前 scene=%s 无转移表，按 A %.2fs",
                            tag,
                            current,
                            duration,
                        )
                        await self._press_button("A", duration=duration)
                else:
                    label_key = (label or "").strip()
                    if (
                        label_key in DISMISS_HOLD_A_UNMATCHED_LABELS
                        and step > 0
                        and step % 3 == 2
                    ):
                        duration = resolve_automation_a_press_sec(
                            102, force_hold=True
                        )
                        self.logger.info(
                            "%s未识别 scene，尝试长按 A %.1fs（过场跳过）",
                            tag,
                            duration,
                        )
                        await self._press_button("A", duration=duration)
                    else:
                        self.logger.warning(
                            "%s模板均未匹配，跳过 A（继续轮询）",
                            tag,
                        )

                step += 1
                if step % 8 == 0:
                    await self._recover_input_if_closed()
                    await self._send_keepalive()
                await asyncio.sleep(1.0)

            self.logger.warning(
                "%sdismiss_until_scenes 超时，未到达 %s",
                tag,
                sorted(targets),
            )
            await self._save_debug_frame(target_scene_ids[0])
            return False

    async def go_to_xbox_home_for_resume(self, timeout: float = 90.0) -> bool:
        """
        恢复自动化：不论当前在 FC/UT 哪一屏，优先按 Xbox(NEXUS) 键回到主机主页。

        用于暂停恢复后重锚，再按 matches_completed_today 跳过已完成进度。
        """
        self.logger.info(
            "恢复重锚：Guide(NEXUS) → Xbox 主页 (timeout=%ss)", timeout
        )
        async with self._stream_keepalive_loop():
            if not await self._ensure_input_ready():
                self.logger.error("go_to_xbox_home_for_resume: input 不可用")
                return False

            deadline = time.time() + timeout
            step = 0
            while time.time() < deadline:
                home = await self._detect_any_scene([203, 1, 24], strict=False)
                if home in XBOX_HOME_SCENES:
                    self.logger.info("恢复重锚：已在 Xbox 主页 scene=%s", home)
                    return True
                if await self._is_home_203_dominant():
                    self.logger.info("恢复重锚：已在 Xbox 主页 (scene203 高置信)")
                    return True

                step += 1
                if step == 1 or step % 8 == 0:
                    await self._press_guide_button()
                elif step % 4 == 0:
                    for _ in range(2):
                        await self._press_button("B", duration=0.1)
                        await asyncio.sleep(0.35)
                else:
                    await self._press_button("B", duration=0.1)

                await asyncio.sleep(0.45)
                if step % 6 == 0:
                    await self._recover_input_if_closed()
                    await self._send_keepalive()

            self.logger.warning("恢复重锚：超时未回到 Xbox 主页")
            await self._save_debug_frame(203)
            return False

    async def _launch_fc_from_home_tile(self) -> bool:
        """在主页 FC 磁贴获焦后按 A 启动；头像获焦时先下移至磁贴，禁止在头像上按 A。"""
        for attempt in range(1, FC_LAUNCH_203_MAX_ATTEMPTS + 1):
            if await self._detect_any_scene(list(FC_UT_TARGET_SCENES), strict=False):
                return True

            if await self._is_profile_avatar_focused() and not await self._is_fc_tile_focused():
                self.logger.info(
                    "启动 FC 前焦点在档案头像，先移至 FC 磁贴（不按 A）"
                )
                await self._ensure_fc_tile_focused_for_launch()

            if not await self._is_fc_tile_focused():
                self.logger.info("启动 FC 前确认磁贴焦点")
                await self._navigate_to_fc_tile_on_home()

            if not await self._is_fc_tile_focused():
                self.logger.warning(
                    "FC 磁贴仍未获焦，跳过本轮 A（避免在头像/顶栏误启动）"
                )
                await self._save_debug_frame(203)
                continue

            if not await self._recover_input_if_closed():
                self.logger.error("启动 FC 时 input 通道不可用")
                await self._save_debug_frame(203)
                return False

            self.logger.info(
                "按 A 启动 FC（第 %s/%s 次）",
                attempt,
                FC_LAUNCH_203_MAX_ATTEMPTS,
            )
            sent = await self._send_raw_controller(16, 0, 0, 0, 0, 0, 0, 0.05)
            if not sent:
                self.logger.warning("A 键发送可能失败（session 未绑定）")
            await asyncio.sleep(0.6)

            wait_s = FC_TRANSITION_POST_WAIT.get(203, 60.0)
            if attempt == 1:
                wait_budget = wait_s
            else:
                wait_budget = min(wait_s, FC_LAUNCH_203_RETRY_INTERVAL + 20.0)

            if await self._wait_for_game_launch_progress(timeout=wait_budget):
                return True

            if attempt < FC_LAUNCH_203_MAX_ATTEMPTS:
                self.logger.warning(
                    "FC 仍在主页 203，%.0fs 后重试 A",
                    FC_LAUNCH_203_RETRY_INTERVAL,
                )
                await asyncio.sleep(FC_LAUNCH_203_RETRY_INTERVAL)

        self.logger.error("FC 从主页启动失败：多次 A 后仍停留 scene203")
        await self._log_scene_probe([203, 101, 126])
        await self._save_debug_frame(203)
        raise ManualInterventionRequired()

    async def _get_normalized_frame(self) -> Optional[Any]:
        if not self._frame_getter:
            return None
        frame = await self._frame_getter()
        if frame is None:
            return None
        image = _extract_frame_image(frame)
        if self._scene_detector:
            return self._scene_detector._normalize_frame(image, 203)
        import cv2
        return cv2.resize(image, (960, 540), interpolation=cv2.INTER_AREA)

    async def _green_ratio_in_region(
        self, region: Tuple[int, int, int, int], *, min_ratio: float = 0.04
    ) -> bool:
        """检测 960x540 坐标系内 Xbox 绿框焦点（streaming 风格区域探针）。"""
        from ..vision.profile_name_reader import _focus_green_ratio

        norm = await self._get_normalized_frame()
        if norm is None:
            return False
        left, top, right, bottom = region
        ratio = _focus_green_ratio(norm, left, top, right, bottom)
        return ratio >= min_ratio

    async def _is_profile_avatar_focused(self) -> bool:
        norm = await self._get_normalized_frame()
        if norm is None:
            return False
        from ..vision.profile_name_reader import is_home_profile_avatar_focused

        return is_home_profile_avatar_focused(norm)

    async def _is_top_settings_focused(self) -> bool:
        from ..vision.profile_name_reader import (
            HOME203_SETTINGS_FOCUS_BOTTOM,
            HOME203_SETTINGS_FOCUS_LEFT,
            HOME203_SETTINGS_FOCUS_RIGHT,
            HOME203_SETTINGS_FOCUS_TOP,
        )

        return await self._green_ratio_in_region(
            (
                HOME203_SETTINGS_FOCUS_LEFT,
                HOME203_SETTINGS_FOCUS_TOP,
                HOME203_SETTINGS_FOCUS_RIGHT,
                HOME203_SETTINGS_FOCUS_BOTTOM,
            ),
            min_ratio=0.08,
        )

    async def _is_fc_tile_focused(self) -> bool:
        norm = await self._get_normalized_frame()
        if norm is None:
            return False
        from ..vision.profile_name_reader import is_home_fc_tile_focused

        return is_home_fc_tile_focused(norm)

    def _scene_match_threshold(self, scene_id: int) -> float:
        """Xbox 系统 UI / 小键盘场景允许略低于 schema 默认阈值的匹配。"""
        # 场景 5/6 在 FC 游戏 Hub 等页面易误匹配，需提高阈值
        if scene_id == 6:
            return 0.95
        if scene_id == 5:
            return 0.88
        if scene_id <= 64:
            return 0.60
        if scene_id in FC_UT_TARGET_SCENES:
            # 126/127 在 Xbox 主页有误匹配（~0.76），提高阈值
            return 0.85
        if scene_id == 203:
            return 0.90
        return getattr(self._scene_detector, 'default_threshold', 0.8)

    async def _wait_for_scene(
        self,
        scene_id: int,
        timeout: float = 20.0,
        *,
        strict: bool = False,
    ) -> bool:
        return await self._wait_for_any_scene(
            [scene_id], timeout=timeout, strict=strict
        )

    async def _wait_for_any_scene(
        self,
        scene_ids: List[int],
        timeout: float = 20.0,
        *,
        strict: bool = False,
        threshold_override: Optional[float] = None,
    ) -> bool:
        """
        轮询截帧直至任一 scene_ids 匹配或超时。

        等待期间：模板未匹配时不盲按 A；每 8s 检测 input 通道并发送 keepalive。
        strict=True 时会额外比对 XBOX_UI_AMBIGUOUS_SCENES 以降低误匹配。
        """
        if not self._scene_detector or not self._frame_getter:
            self.logger.warning(f"跳过场景校验 {scene_ids}（未绑定检测器或截帧）")
            return True

        deadline = time.time() + timeout
        last_keepalive = 0.0
        while time.time() < deadline:
            matched = await self._detect_any_scene(
                scene_ids,
                strict=strict,
                threshold_override=threshold_override,
            )
            if matched is not None:
                self.logger.info(f"场景{matched}校验通过")
                frame = await self._frame_getter()
                if frame is not None:
                    image = _extract_frame_image(frame)
                    scores = await self._score_scenes([matched], image)
                    conf = scores.get(matched)
                    await self._capture_detected_scene(
                        matched,
                        image,
                        confidence=conf,
                        note="wait_for_scene",
                    )
                return True
            now = time.time()
            if now - last_keepalive >= 8.0:
                if not await self._recover_input_if_closed():
                    self.logger.warning(
                        f"等待场景 {scene_ids} 时 input 通道不可用"
                    )
                else:
                    await self._send_keepalive()
                last_keepalive = now
            await asyncio.sleep(0.5)

        self.logger.warning(f"场景校验超时 {scene_ids} ({timeout}s)")
        await self._log_scene_probe(scene_ids)
        await self._save_debug_frame(scene_ids[0] if scene_ids else 0)
        return False

    async def _score_scenes(
        self,
        scene_ids: List[int],
        image: Any,
        threshold_override: Optional[float] = None,
    ) -> Dict[int, float]:
        scores: Dict[int, float] = {}
        if not self._scene_detector:
            return scores
        for scene_id in scene_ids:
            threshold = (
                threshold_override
                if threshold_override is not None
                else self._scene_match_threshold(scene_id)
            )
            result = self._scene_detector.recognize_scene(
                image, scene_id=scene_id, threshold=threshold
            )
            if result.matched:
                scores[scene_id] = result.confidence
        return scores

    async def _detect_any_scene(
        self,
        scene_ids: List[int],
        *,
        strict: bool = False,
        threshold_override: Optional[float] = None,
    ) -> Optional[int]:
        if not self._scene_detector or not self._frame_getter:
            return None

        frame = await self._frame_getter()
        if frame is None:
            return None
        image = _extract_frame_image(frame)

        compare_ids = list(dict.fromkeys(scene_ids))
        if strict:
            compare_ids = list(
                dict.fromkeys(compare_ids + XBOX_UI_AMBIGUOUS_SCENES)
            )

        scores = await self._score_scenes(
            compare_ids, image, threshold_override=threshold_override
        )
        if not scores:
            return None

        if not strict:
            best_id = None
            best_conf = 0.0
            for scene_id in scene_ids:
                conf = scores.get(scene_id, 0.0)
                if threshold_override is not None:
                    thr = threshold_override
                else:
                    thr = self._scene_match_threshold(scene_id)
                if conf >= thr and conf > best_conf:
                    best_conf = conf
                    best_id = scene_id
            if best_id is not None:
                self._cache_detected_scene_id(best_id)
            return best_id

        target_scores = {sid: scores.get(sid, 0.0) for sid in scene_ids}
        best_id = max(target_scores, key=target_scores.get)
        best_conf = target_scores[best_id]
        if best_conf < self._scene_match_threshold(best_id):
            return None
        for amb_id in XBOX_UI_AMBIGUOUS_SCENES:
            if amb_id in scene_ids:
                continue
            amb_conf = scores.get(amb_id, 0.0)
            if amb_conf > best_conf + 0.03:
                return None
        self._cache_detected_scene_id(best_id)
        return best_id

    def _cache_detected_scene_id(self, scene_id: int) -> None:
        ctx = getattr(self, "_task_context", None)
        if ctx is None:
            return
        from ..input.manual_nav import update_last_streaming_scene_id

        update_last_streaming_scene_id(ctx, scene_id)

    async def _log_scene_probe(self, scene_ids: List[int]) -> None:
        """场景校验失败时输出候选场景置信度，便于联调。"""
        if not self._scene_detector or not self._frame_getter:
            return
        frame = await self._frame_getter()
        if frame is None:
            self.logger.warning("场景探针：当前帧为空")
            return
        image = _extract_frame_image(frame)
        probe_ids = list(dict.fromkeys(scene_ids + XBOX_UI_AMBIGUOUS_SCENES))
        scores = await self._score_scenes(probe_ids, image)
        if not scores:
            self.logger.warning("场景探针：无场景通过阈值")
            return
        ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
        summary = ", ".join(f"{sid}={conf:.3f}" for sid, conf in ranked[:8])
        self.logger.warning(f"场景探针 Top: {summary}")

    async def _save_debug_frame(self, scene_id: int):
        """场景校验失败时保存当前帧，便于对比模板。"""
        if not self._frame_getter:
            return
        try:
            import os
            import cv2

            frame = await self._frame_getter()
            if frame is None:
                return
            image = _extract_frame_image(frame)
            log_dir = get_logs_dir_fallback()
            os.makedirs(log_dir, exist_ok=True)
            path = os.path.join(log_dir, f"debug_scene{scene_id}_{int(time.time())}.png")
            if not cv2.imwrite(path, image):
                self.logger.warning(f"保存场景{scene_id}调试帧失败: cv2.imwrite 返回 False, path={path}")
                return
            self.logger.warning(f"已保存场景{scene_id}调试帧: {os.path.abspath(path)}")
        except Exception as e:
            self.logger.debug(f"保存调试帧失败: {e}")

    def _resolve_input_session(self):
        """从串流绑定或动作执行器解析 SmartGlass 会话。"""
        if self._stream_session is not None:
            return self._stream_session
        executor = self._action_executor
        if executor is None:
            return None
        session = getattr(executor, "_xbox_session", None)
        if session is not None:
            return session
        return getattr(executor, "_stream_controller", None)

    async def _execute_press_button(self, button: str, duration: float = 0.08) -> None:
        if not self._action_executor:
            return
        from ..scene.game_automation_engine import Action, ActionType

        if hasattr(self._action_executor, "execute"):
            await self._action_executor.execute(
                Action(
                    type=ActionType.PRESS_BUTTON,
                    params={'button': button, 'duration': duration},
                    description=f"Press {button}",
                    timeout=2.0,
                )
            )
            return

        from ..input.controller_protocol import ControllerProtocol, XboxButtonFlag

        if isinstance(self._action_executor, ControllerProtocol):
            flag_name = button.upper()
            if not hasattr(XboxButtonFlag, flag_name):
                self.logger.warning("未知手柄按钮: %s", button)
                return
            await self._action_executor.press_button(
                getattr(XboxButtonFlag, flag_name),
                duration,
            )

    async def _press_button(self, button: str, duration: float = 0.08):
        if not self._action_executor:
            return
        log_gamepad_input(
            button,
            duration=duration,
            source="account_switcher",
            task_id=self._trace_task_id(),
        )
        await self._ensure_input_ready()
        await self._execute_press_button(button, duration)

    async def _press_guide_button(self):
        await self._press_button('NEXUS', duration=0.05)
        await asyncio.sleep(0.8)

    async def _is_guide_visible(self) -> bool:
        """引导页可见：场景2 置信度高于主页/误匹配场景6。"""
        if not self._scene_detector or not self._frame_getter:
            return False
        frame = await self._frame_getter()
        if frame is None:
            return False
        image = _extract_frame_image(frame)
        scores = await self._score_scenes([2, 3, 6, 203, 1], image)
        guide_score = scores.get(2, 0.0)
        if guide_score < self._scene_match_threshold(2):
            return False
        home_score = max(scores.get(203, 0.0), scores.get(1, 0.0))
        noise_score = scores.get(6, 0.0)
        return guide_score > home_score and guide_score >= noise_score

    async def _wait_for_guide(self, timeout: float = 8.0) -> bool:
        deadline = time.time() + timeout
        while time.time() < deadline:
            if await self._is_guide_visible():
                self.logger.info("场景2校验通过（引导页）")
                return True
            await asyncio.sleep(0.5)
        return False

    async def _open_guide_menu(self) -> bool:
        """打开西瓜引导页（场景2）；主页 NEXUS 失败则改走设置→账号（场景3）。"""
        if await self._wait_for_guide(timeout=2.0):
            return True
        if await self._wait_for_scene(3, timeout=1.5):
            self.logger.info("已在场景3，无需打开引导页")
            return True

        on_home = await self._detect_any_scene([203, 1, 24], strict=False)
        if on_home in XBOX_HOME_SCENES:
            self.logger.info("尝试打开引导页: NEXUS-from-home")
            await self._press_guide_button()
            if await self._wait_for_guide(timeout=5.0):
                return True
            self.logger.info("NEXUS 未打开引导页，改走主页→设置→账号")
            await self._navigate_to_accounts_from_home()
            if await self._wait_for_scene(3, timeout=12.0):
                return True
            return False

        self.logger.info("尝试打开引导页: scene_transition 1/1")
        await self._run_scene_transition(1, 1)
        if await self._wait_for_guide(timeout=5.0):
            return True

        self.logger.info("尝试打开引导页: NEXUS")
        await self._press_guide_button()
        return await self._wait_for_guide(timeout=5.0)

    async def _navigate_to_accounts_from_home(self):
        """从 Xbox 主页顶栏进入「设置」→ 账号相关页面。"""
        self.logger.info("从主页经设置进入档案和系统")
        for _ in range(3):
            await self._press_button("B", duration=0.08)
            await asyncio.sleep(0.2)
        for _ in range(5):
            await self._press_button("DPAD_RIGHT", duration=0.08)
            await asyncio.sleep(0.15)
        await self._press_button("A", duration=0.08)
        await asyncio.sleep(1.2)
        for _ in range(4):
            await self._press_button("DPAD_DOWN", duration=0.08)
            await asyncio.sleep(0.2)
        await self._press_button("A", duration=0.08)
        await asyncio.sleep(1.5)

    async def _navigate_to_accounts_system(self):
        """从西瓜引导页侧栏进入「档案和系统」。"""
        for i in range(5):
            if not self._action_executor:
                return
            await self._execute_press_button('DPAD_DOWN', duration=0.05)
            await asyncio.sleep(0.25)

        await self._press_button('A', duration=0.05)
        await asyncio.sleep(1.2)

    async def _select_add_switch(self) -> bool:
        """
        场景3 → 场景5：须 strict 确认场景3，且不在引导/主页误页按 A。

        按 A 后若未进入场景5 立即中止，不再 DPAD 盲重试（避免误触 FC/其它项）。
        """
        if not await self._wait_for_scene(3, timeout=1.5, strict=True):
            self.logger.warning("_select_add_switch: 未在场景3，跳过盲按 A")
            return False

        if await self._wait_for_scene(5, timeout=1.0, strict=True):
            return True

        if await self._is_scene6_template_without_layout(strict=True):
            self.logger.warning(
                "当前页似场景6但无档案列表（可能为游戏 Hub），拒绝盲按 A"
            )
            await self._save_debug_frame(6)
            return False

        dominant = await self._detect_any_scene([2, 24, 3], strict=False)
        if dominant in (2, 24):
            self.logger.warning(
                "_select_add_switch: 当前仍似引导/主页 (scene=%s)，不按 A",
                dominant,
            )
            await self._save_debug_frame(dominant or 3)
            return False

        await self._press_button('A', duration=0.08)
        if await self._wait_for_scene(5, timeout=4.0, strict=True):
            return True

        self.logger.warning(
            "_select_add_switch: 按 A 后未进入场景5，中止（不再盲重试 DPAD+A）"
        )
        await self._save_debug_frame(5)
        return False

    async def _enter_account_selection(self) -> bool:
        """
        场景5 → 场景6：须先确认场景5，且不在误匹配页按 A；进入后须模板+布局双确认。
        """
        if await self._wait_for_scene6_confirmed(timeout=1.5, strict=True):
            return True

        if not await self._wait_for_scene(5, timeout=3.0, strict=True):
            self.logger.warning("_enter_account_selection: 场景5未确认，不按 A")
            await self._save_debug_frame(5)
            return False

        if await self._is_scene6_template_without_layout(strict=True):
            self.logger.warning(
                "_enter_account_selection: 场景5后页面似误匹配场景6，不按 A"
            )
            await self._save_debug_frame(6)
            return False

        await self._press_button('A', duration=0.1)
        await asyncio.sleep(1.5)
        return await self._wait_for_scene6_confirmed(timeout=12.0, strict=True)

    async def _read_host_gamertag_from_profile_list(self) -> Optional[str]:
        """
        登录/添加用户后进入场景6，OCR 读取列表最上方档案昵称（主机侧 Gamertag）。
        """
        for _ in range(3):
            await self._press_button('B', duration=0.08)
            await asyncio.sleep(0.35)

        if not await self._open_guide_menu():
            await self._navigate_to_accounts_system()
        elif not await self._run_scene_transition(2, 2):
            await self._navigate_to_accounts_system()

        if not await self._wait_for_scene(3, timeout=12.0):
            self.logger.warning("读取主机昵称：未能进入场景3")
            await self._save_debug_frame(3)
            return None

        await self._select_add_switch()
        if not await self._wait_for_scene(5, timeout=12.0):
            self.logger.warning("读取主机昵称：未能进入场景5")
            return None

        if not await self._enter_account_selection():
            self.logger.warning("读取主机昵称：未能进入场景6（模板+布局）")
            return None

        await self._scroll_profile_list_to_top()
        await asyncio.sleep(0.45)
        detected = await self._read_focused_gamertag_from_frame()
        if detected and detected.strip():
            self.logger.info("主机档案昵称 OCR: %r", detected.strip())
            return detected.strip()

        self.logger.warning("场景6未能 OCR 到主机档案昵称")
        await self._save_debug_frame(6)
        return None

    async def add_new_user_with_credentials(
        self,
        email: str,
        password: str,
        check_cancel: Optional[Callable[[], bool]] = None,
        *,
        account_id: Optional[str] = None,
    ) -> AccountSwitchResult:
        """被动开通：导航到添加用户流程并用凭证登录。"""
        start = time.time()
        host_tag: Optional[str] = None
        try:
            if check_cancel and check_cancel():
                return AccountSwitchResult(success=False, error_message="cancelled")

            async with self._stream_keepalive_loop():
                await self._ensure_input_ready()
                if not await self._open_guide_menu():
                    await self._navigate_to_accounts_system()
                elif not await self._run_scene_transition(2, 2):
                    await self._navigate_to_accounts_system()

                if not await self._wait_for_scene(3):
                    raise RuntimeError("未进入档案和系统页面（场景3）")

                stub = GameAccount(
                    account_id=account_id or "",
                    gamertag="",
                    email=email,
                    password=password,
                )
                from .scenes.add_account import AddAccountScene

                await AddAccountScene(self).run(stub)
                host_tag = stub.host_display_name or stub.gamertag or None

            return AccountSwitchResult(
                success=True,
                to_account=email,
                time_taken=time.time() - start,
                host_gamertag=host_tag,
            )
        except Exception as exc:
            self.logger.error("add_new_user_with_credentials failed: %s", exc)
            return AccountSwitchResult(
                success=False,
                error_message=str(exc),
                time_taken=time.time() - start,
            )

    async def _select_add_new_user(self):
        """场景5/6 滚到底部选中「添加新用户」（绿框 Y 触底探针）。"""
        self.logger.info("选择「添加新用户」")
        if not await self._ensure_scene6_add_new_user_focused():
            self.logger.warning("未能确认「添加新用户」获焦，仍尝试按 A")
        await self._press_button("A", duration=0.1)
        await asyncio.sleep(2.0)

    async def _scroll_profile_list_to_top(self) -> None:
        for _ in range(10):
            await self._press_button('DPAD_UP', duration=0.1)
            await asyncio.sleep(0.15)

    async def _read_focused_gamertag_from_frame(self) -> str:
        from ..vision.profile_name_reader import read_focused_gamertag

        frame = await self._frame_getter() if self._frame_getter else None
        if frame is None:
            return ""
        image = _extract_frame_image(frame)
        if self._scene_detector and hasattr(self._scene_detector, '_normalize_frame'):
            image = self._scene_detector._normalize_frame(image, 6)
        return read_focused_gamertag(image)

    async def _select_account_by_gamertag(
        self,
        gamertag: str,
        *,
        email: Optional[str] = None,
        host_display_name: Optional[str] = None,
        max_slots: Optional[int] = None,
    ) -> Optional[int]:
        """
        在场景6列表中按 gamertag / 邮箱 / 主机显示名 查找档案。

        返回匹配到的列表索引（0=最上方）；扫尽未找到返回 None。
        """
        from ..vision.profile_name_reader import (
            account_identity_matches,
            is_scene6_add_guest_row,
            is_scene6_add_new_user_row,
            read_list_gamertags,
        )

        if not gamertag and not email:
            raise RuntimeError("目标 gamertag/email 为空，无法定位档案")

        if not await self._verify_scene6_layout():
            await self._save_debug_frame(6)
            raise RuntimeError("场景6列表 OCR 前布局校验失败")

        await self._scroll_profile_list_to_top()
        await asyncio.sleep(0.35)

        if max_slots is None:
            max_slots = self._scene6_max_down_steps()
        unchanged_steps = 0
        threshold = self._scene6_focus_unchanged_threshold()
        prev_y = await self._read_scene6_focus_y()

        for slot in range(max_slots):
            detected = await self._read_focused_gamertag_from_frame()

            if is_scene6_add_new_user_row(detected):
                self.logger.info(
                    "场景6 已到达「添加新用户」行，未找到档案 %s", gamertag
                )
                await self._save_debug_frame(6)
                return None

            if not is_scene6_add_guest_row(detected) and account_identity_matches(
                detected,
                gamertag=gamertag,
                email=email,
                host_display_name=host_display_name,
            ):
                self.logger.info(
                    "场景6已定位档案 %s（列表索引 %s，OCR=%r）",
                    gamertag,
                    slot,
                    detected,
                )
                return slot

            if slot == 0 and not detected:
                frame = await self._frame_getter() if self._frame_getter else None
                if frame is not None:
                    image = _extract_frame_image(frame)
                    if self._scene_detector and hasattr(
                        self._scene_detector, "_normalize_frame"
                    ):
                        image = self._scene_detector._normalize_frame(image, 6)
                    for line in read_list_gamertags(image):
                        if account_identity_matches(
                            line,
                            gamertag=gamertag,
                            email=email,
                            host_display_name=host_display_name,
                        ):
                            self.logger.info(
                                "场景6列表 OCR 匹配档案 %s（索引 %s，OCR=%r）",
                                gamertag,
                                slot,
                                line,
                            )
                            return slot

            await self._press_button("DPAD_DOWN", duration=0.1)
            await asyncio.sleep(0.35)
            new_y = await self._read_scene6_focus_y()
            if new_y is not None and prev_y is not None and new_y == prev_y:
                unchanged_steps += 1
                if unchanged_steps >= threshold:
                    self.logger.info(
                        "场景6 绿框 Y 连续 %s 次未变，列表扫尽（slot=%s）",
                        threshold,
                        slot,
                    )
                    await self._save_debug_frame(6)
                    return None
            else:
                unchanged_steps = 0
            prev_y = new_y

        await self._save_debug_frame(6)
        self.logger.info(
            "场景6 达到最大 DOWN 步数 (%s)，未找到档案 %s", max_slots, gamertag
        )
        return None

    async def _confirm_account_selection(self):
        if not await self._verify_scene6_layout():
            await self._save_debug_frame(6)
            raise RuntimeError("确认档案前场景6布局校验失败")
        await self._press_button('A', duration=0.1)
        await asyncio.sleep(2.0)

    async def _recover_input_if_closed(self) -> bool:
        """input closed 时调度后台重连，短时轮询 open；不阻塞在全量 WebRTC 握手。"""
        import time

        from ..core.config import config as app_config
        from ..xbox.controller_write import schedule_input_reconnect
        from ..xbox.stream_keepalive import (
            get_input_channel_state,
            is_input_channel_open,
            send_keepalive,
        )

        if self._stream_session is None:
            return True

        ctx = getattr(self, "_task_context", None)
        force_reconnect = bool(
            ctx is not None and getattr(ctx, "_input_channel_dirty", False)
        )
        if not force_reconnect and is_input_channel_open(self._stream_session):
            await send_keepalive(self._stream_session, context=ctx)
            return True

        channel_state = get_input_channel_state(self._stream_session)
        if ctx is not None:
            ctx._input_channel_dirty = True

        self.logger.warning(
            "input DataChannel 不可用 (state=%s)，调度后台重连",
            channel_state,
        )
        schedule_input_reconnect(ctx)

        wait_sec = float(app_config.get("gssv.input_reconnect_wait_sec", 8))
        deadline = time.time() + wait_sec
        while time.time() < deadline:
            if is_input_channel_open(self._stream_session):
                await send_keepalive(self._stream_session, context=ctx)
                self.logger.info("input 通道已恢复 open")
                if ctx is not None:
                    ctx._input_channel_dirty = False
                return True
            await asyncio.sleep(0.25)

        self.logger.warning(
            "input 通道 %ss 内未恢复，跳过当前步骤",
            wait_sec,
        )
        return False

    async def _ensure_input_ready(self) -> bool:
        return await self._recover_input_if_closed()

    async def _send_keepalive(self) -> None:
        from ..xbox.stream_keepalive import send_keepalive
        if self._stream_session is not None:
            await send_keepalive(
                self._stream_session,
                context=getattr(self, "_task_context", None),
            )

    async def _login_with_credentials(self, email: str, password: str):
        """微软账号登录：场景10 + 小键盘输入。"""
        from .on_screen_keyboard import OnScreenKeyboard

        self.logger.info("开始微软账号登录流程")
        if not await self._wait_for_scene(10, timeout=45.0):
            await self._save_debug_frame(10)
            raise RuntimeError("未进入微软登录页（场景10）")

        keyboard = OnScreenKeyboard(
            self._action_executor,
            self._scene_detector,
            self._frame_getter,
            threshold=self._scene_match_threshold(30),
            stream_session=self._stream_session,
        )

        async with self._stream_keepalive_loop():
            await self._ensure_input_ready()
            await self._press_button('A', duration=0.1)
            await asyncio.sleep(0.5)
            await keyboard.ensure_open()
            await keyboard.type_text(email, timeout_per_char=5.0)

            await self._press_button('RB', duration=0.08)
            await asyncio.sleep(0.4)
            if not await self._wait_for_scene(10, timeout=3.0):
                await self._press_button('DPAD_DOWN', duration=0.08)
                await asyncio.sleep(0.3)
            await self._press_button('A', duration=0.08)
            await asyncio.sleep(0.8)
            await keyboard.ensure_open()
            await keyboard.type_text(password, timeout_per_char=5.0)
            await self._press_button('A', duration=0.1)
            await asyncio.sleep(3.0)

            await self._dismiss_post_login_prompts()

    async def _dismiss_post_login_prompts(self):
        """跳过 Game Pass 等首登弹窗，尽量回到主机主页。"""
        for _ in range(6):
            if await self._detect_any_scene([1, 24, 203, 95, 101], strict=False):
                return
            await self._press_button('B', duration=0.08)
            await asyncio.sleep(0.8)
            await self._press_button('A', duration=0.08)
            await asyncio.sleep(0.5)

    async def run_scene_transition_chain(
        self,
        chain: List[Tuple[int, int]],
        *,
        label: str = "",
        complete_scenes: Optional[set] = None,
    ) -> bool:
        """按 SCENE_TRANSITIONS 顺序执行多步转移。"""
        if not chain:
            return True

        tag = f"[{label}] " if label else ""
        self.logger.info(f"{tag}开始场景转移链 ({len(chain)} 步): {chain}")

        for scene_id, transition_id in chain:
            if complete_scenes:
                hit = await self._detect_any_scene(list(complete_scenes), strict=False)
                if hit in complete_scenes:
                    self.logger.info(f"{tag}已到达目标 scene {hit}，提前结束链")
                    return True

            from configs.scene_transitions import get_transition

            transition = get_transition(scene_id, transition_id)
            if transition:
                self.logger.info(
                    f"{tag}执行转移 {scene_id}/{transition_id}: {transition.get('description', '')}"
                )

            ok = await self._run_scene_transition(scene_id, transition_id)
            if not ok:
                self.logger.warning(
                    f"{tag}场景转移未确认: {scene_id}/{transition_id}"
                )
                await self._save_debug_frame(scene_id)
                return False
            await asyncio.sleep(0.4)

        return True

    async def _run_scene_transition(self, scene_id: int, transition_id: int) -> bool:
        """执行 scene_transitions 中定义的单步转移。"""
        from configs.scene_transitions import get_transition

        transition = get_transition(scene_id, transition_id)
        if not transition:
            self.logger.warning(f"未找到场景转移配置: {scene_id}/{transition_id}")
            return False

        target_scenes = transition['target_scenes']
        for option in transition['controller_options']:
            duration_ms, count, buttons, lt, rt, lx, ly, rx, ry = option
            max_attempts = count if count > 0 else 20
            for _ in range(max_attempts):
                if not await self._ensure_input_ready():
                    return False
                await self._send_raw_controller(
                    buttons, lt, rt, lx, ly, rx, ry, duration_ms / 1000.0
                )
                await asyncio.sleep(0.45)
                strict_targets = not any(t in FC_UT_TARGET_SCENES for t in target_scenes)
                if await self._detect_any_scene(target_scenes, strict=strict_targets):
                    return True

        post_wait = FC_TRANSITION_POST_WAIT.get(scene_id, 0.0)
        strict_targets = not any(t in FC_UT_TARGET_SCENES for t in target_scenes)
        launch_threshold = None
        if 101 in target_scenes:
            launch_threshold = FC_LAUNCH_101_THRESHOLD
        if post_wait > 0:
            self.logger.info(
                f"场景 {scene_id} 转移后等待目标 {target_scenes}（最长 {post_wait}s）"
            )
            return await self._wait_for_any_scene(
                target_scenes,
                timeout=post_wait,
                strict=strict_targets,
                threshold_override=launch_threshold,
            )

        matched = await self._detect_any_scene(
            target_scenes, strict=strict_targets, threshold_override=launch_threshold
        )
        return matched is not None

    async def _send_raw_controller(
        self,
        buttons: int,
        left_trigger: int,
        right_trigger: int,
        left_thumb_x: int,
        left_thumb_y: int,
        right_thumb_x: int,
        right_thumb_y: int,
        duration_sec: float,
    ):
        if buttons:
            log_gamepad_input(
                f"RAW_MASK",
                duration=duration_sec,
                source="account_switcher.raw",
                raw_buttons=buttons,
                task_id=self._trace_task_id(),
            )
        if self._input_gate is not None and not self._input_gate.is_allowed():
            return False

        ctx = getattr(self, "_task_context", None)
        if ctx is not None and getattr(ctx, "_manual_takeover", False):
            return False

        session = self._resolve_input_session()
        if session is None:
            await asyncio.sleep(duration_sec)
            return False

        from ..input.controller_protocol import ControllerSignal

        press = ControllerSignal(
            buttons=buttons,
            left_trigger=left_trigger,
            right_trigger=right_trigger,
            left_thumb_x=left_thumb_x,
            left_thumb_y=left_thumb_y,
            right_thumb_x=right_thumb_x,
            right_thumb_y=right_thumb_y,
        )
        release = ControllerSignal()

        async def _do_send() -> bool:
            from ..xbox.controller_write import write_controller_final

            active_session = self._resolve_input_session()
            ctx = getattr(self, "_task_context", None)
            if active_session is None:
                return False
            try:
                if hasattr(active_session, 'send_gamepad_state'):
                    ok_press = await write_controller_final(
                        active_session, press.to_dict(), context=ctx
                    )
                    await asyncio.sleep(max(duration_sec, 0.05))
                    ok_release = await write_controller_final(
                        active_session, release.to_dict(), context=ctx
                    )
                    return ok_press and ok_release
                if hasattr(active_session, 'send_input'):
                    await active_session.send_input('gamepad', press.to_dict())
                    await asyncio.sleep(max(duration_sec, 0.05))
                    await active_session.send_input('gamepad', release.to_dict())
                    return True
            except Exception as e:
                self.logger.warning(f"发送原始手柄信号失败: {e}")
            return False

        if not await _do_send():
            self.logger.warning("手柄信号发送失败，尝试恢复 input 通道后重试")
            if await self._recover_input_if_closed():
                if not await _do_send():
                    self.logger.error("手柄信号重试后仍发送失败")
                    return False
            else:
                return False
        await asyncio.sleep(0.05)
        return True

    async def validate_current(self) -> bool:
        if not self._current_account_id:
            return False
        current = self._accounts.get(self._current_account_id)
        if not current:
            return False
        if current.status == AccountStatus.LOGGED_IN:
            return True
        if current.last_login and (time.time() - current.last_login) > 3600:
            self.logger.warning("账号登录已超过1小时，可能需要重新验证")
            return False
        return True

    def reset_all_daily_counts(self):
        for account in self._accounts.values():
            account.reset_daily_count()
        self.logger.info("所有账号每日计数已重置")


account_switcher = AccountSwitcher()
