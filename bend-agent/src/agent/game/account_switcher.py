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
from typing import Optional, Dict, List, Any, Callable, Awaitable, Tuple
from dataclasses import dataclass
from enum import Enum
import time

from ..core.logger import get_logger


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
    profile_bound: bool = False
    status: AccountStatus = AccountStatus.UNKNOWN
    last_login: Optional[float] = None
    matches_today: int = 0
    max_matches_per_day: int = 3

    def is_available(self) -> bool:
        return self.matches_today < self.max_matches_per_day

    def needs_credential_login(self) -> bool:
        """新号或未完成主机绑定时才走凭据登录。"""
        if not (self.email and self.password):
            return False
        if self.is_new_user:
            return True
        return not self.profile_bound

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

# Xbox「您是谁」列表最大扫描行数（含「添加新用户」前的档案）
MAX_PROFILE_LIST_SLOTS = 12


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
            Callable[[str, int, Optional[str]], Awaitable[None]]
        ] = None
        self._input_gate = None

    def set_input_gate(self, gate) -> None:
        """绑定输入闸门（task 级），用于在任务暂停时屏蔽手柄信号。"""
        self._input_gate = gate

    def set_accounts(self, accounts: List[Dict[str, Any]]) -> None:
        """加载游戏账号列表（替换现有账号集合）。"""
        self._accounts.clear()
        for idx, acc_data in enumerate(accounts):
            raw_index = acc_data.get('position_index', idx)
            position_index = idx if raw_index is None or raw_index < 0 else raw_index
            account = GameAccount(
                account_id=acc_data.get('account_id', ''),
                gamertag=acc_data.get('gamertag', ''),
                email=acc_data.get('email'),
                password=acc_data.get('password'),
                xuid=acc_data.get('xuid'),
                position_index=position_index,
                is_new_user=bool(acc_data.get('is_new_user', False)),
                profile_bound=bool(acc_data.get('profile_bound', False)),
                max_matches_per_day=acc_data.get('max_matches_per_day', 3),
            )
            self._accounts[account.account_id] = account

        self.logger.info(f"已加载 {len(self._accounts)} 个游戏账号")
        for acc in self._accounts.values():
            if acc.is_new_user:
                kind = "新用户"
            elif acc.profile_bound:
                kind = "已绑定档案"
            else:
                kind = "已有档案"
            self.logger.info(f"  - {acc.gamertag} ({kind}, 位置: {acc.position_index})")

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
        """设置 input DataChannel 关闭时的重连回调（复用 PlaySession + SDP）。"""
        self._reconnect_callback = callback
        self.logger.info("账号切换器已绑定输入通道重连回调")

    def set_task_context(self, context: Any):
        """绑定任务上下文，用于重连后清除 input dirty 标记。"""
        self._task_context = context

    def set_profile_bound_callback(
        self,
        callback: Optional[Callable[[str, int, Optional[str]], Awaitable[None]]],
    ) -> None:
        """登录/切换成功后回写平台 profile_bound / 主机 Gamertag。"""
        self._profile_bound_callback = callback

    async def _persist_profile_bound(
        self,
        account: GameAccount,
        *,
        host_gamertag: Optional[str] = None,
    ) -> None:
        """切换/登录成功后回写平台：profile_bound=True，position_index=0，可选 gameName。"""
        newly_bound = not account.profile_bound
        account.profile_bound = True
        account.position_index = 0
        resolved_name = (host_gamertag or "").strip() or None
        if resolved_name:
            account.gamertag = resolved_name
        if newly_bound:
            self.logger.info(
                "已标记档案 %s 为主机已绑定 (profile_bound=True)",
                account.gamertag or account.account_id,
            )
        if not self._profile_bound_callback:
            return
        try:
            await self._profile_bound_callback(
                account.account_id,
                0,
                resolved_name,
            )
        except Exception as exc:
            self.logger.warning("profile_bound 平台回写失败: %s", exc)

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

    async def switch_to(self, target_account_id: str) -> AccountSwitchResult:
        """
        切换至目标游戏账号（Step4 账号轮询主入口）。

        流程：StreamKeepaliveLoop 保活 → 确保 input 通道 → 引导菜单/主页导航
        → 按 profile_bound / is_new_user 分支（OCR 选档或新用户登录）→ 回写 profile_bound。
        退出：成功更新 _current_account_id；失败返回 AccountSwitchResult(success=False)。
        """
        start_time = time.time()
        from_account = self._current_account_id

        if target_account_id == from_account:
            return AccountSwitchResult(
                success=True,
                from_account=from_account,
                to_account=target_account_id,
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
            f"切换账号: {from_account} -> {target_account_id} "
            f"({target_account.gamertag}, 位置: {target_account.position_index}, "
            f"新用户: {target_account.is_new_user})"
        )

        try:
            from ..xbox.stream_keepalive import StreamKeepaliveLoop

            async with StreamKeepaliveLoop(lambda: self._stream_session):
                await self._ensure_input_ready()
                on_home = await self._detect_any_scene([203, 1, 24], strict=False)
                if not await self._open_guide_menu():
                    self.logger.warning("未能打开西瓜引导页（场景2），继续尝试导航")
                    if on_home in XBOX_HOME_SCENES or on_home is None:
                        await self._navigate_to_accounts_from_home()
                    else:
                        await self._navigate_to_accounts_system()
                elif not await self._run_scene_transition(2, 2):
                    self.logger.warning("场景转移 2->3 未确认，回退到手动导航")
                    await self._navigate_to_accounts_system()

                if not await self._wait_for_scene(3):
                    await self._log_scene_probe([2, 3, 5])
                    await self._save_debug_frame(3)
                    raise RuntimeError("未进入档案和系统页面（场景3）")

                if target_account.is_new_user and target_account.needs_credential_login():
                    await self._select_add_switch()
                    if not await self._wait_for_scene(5, timeout=15.0):
                        raise RuntimeError("未进入添加和切换页面（场景5）")
                    await self._select_add_new_user()
                    await self._login_with_credentials(
                        target_account.email, target_account.password
                    )
                    host_tag = await self._read_host_gamertag_from_profile_list()
                    await self._persist_profile_bound(
                        target_account, host_gamertag=host_tag
                    )
                else:
                    await self._select_add_switch()
                    if not await self._wait_for_scene(5):
                        raise RuntimeError("未进入添加和切换页面（场景5）")

                    await self._enter_account_selection()
                    if not await self._wait_for_scene(6):
                        raise RuntimeError("未进入账号选择页面（场景6）")

                    found_index = await self._select_account_by_gamertag(
                        target_account.gamertag
                    )
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
                            await self._persist_profile_bound(
                                target_account, host_gamertag=host_tag
                            )
                        else:
                            raise RuntimeError(
                                f"档案 {target_account.gamertag} 需重新登录，"
                                "但未配置邮箱/密码凭据"
                            )
                    else:
                        self.logger.info(
                            "档案切换完成，未出现登录页 (%s, profile_bound=%s)",
                            target_account.gamertag,
                            target_account.profile_bound,
                        )
                        host_tag = await self._read_host_gamertag_from_profile_list()
                        await self._persist_profile_bound(
                            target_account, host_gamertag=host_tag
                        )

            self._current_account_id = target_account_id
            target_account.mark_login()

            time_taken = time.time() - start_time
            self.logger.info(f"账号切换成功: {target_account_id} (耗时: {time_taken:.2f}s)")
            return AccountSwitchResult(
                success=True,
                from_account=from_account,
                to_account=target_account_id,
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
            self.logger.error(f"账号切换失败: {e}")
            return AccountSwitchResult(
                success=False,
                from_account=from_account,
                to_account=target_account_id,
                error_message=str(e),
                time_taken=time.time() - start_time,
            )

    async def launch_fc_to_ut_menu(self, timeout: float = 90.0) -> bool:
        """切换账号后从 Xbox 主页启动 FC 并进入 UT 相关界面。"""
        from ..xbox.stream_keepalive import StreamKeepaliveLoop

        self.logger.info("开始启动 FC 并导航至 UT 界面")
        if not await self._ensure_input_ready():
            self.logger.error("进游戏前 input DataChannel 不可用，中止启动 FC")
            return False

        async with StreamKeepaliveLoop(lambda: self._stream_session):
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
            await self._navigate_to_fc_tile_on_home()
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

        return await self._wait_for_any_scene(list(FC_UT_TARGET_SCENES), timeout=timeout)

    async def _navigate_to_fc_tile_on_home(self):
        """从 Xbox 主页（顶栏可能聚焦「设置」）移焦到 FC 游戏磁贴。"""
        self.logger.info("导航至 FC 游戏磁贴（离开顶栏设置焦点）")
        for _ in range(4):
            await self._press_button('B', duration=0.08)
            await asyncio.sleep(0.3)
        if await self._is_top_settings_focused():
            self.logger.info("顶栏「设置」仍获焦，追加 B 退出")
            for _ in range(2):
                await self._press_button('B', duration=0.08)
                await asyncio.sleep(0.25)
        for _ in range(3):
            await self._press_button('DPAD_DOWN', duration=0.1)
            await asyncio.sleep(0.25)
        for _ in range(6):
            if await self._is_fc_tile_focused():
                self.logger.info("FC 磁贴绿框焦点已确认")
                return
            await self._press_button('DPAD_LEFT', duration=0.1)
            await asyncio.sleep(0.2)
        if await self._detect_any_scene([203], strict=False) == 203:
            self.logger.info("scene203 校验通过（FC 磁贴可见）")
        else:
            self.logger.warning("FC 磁贴焦点未确认 (scene203)，仍尝试启动游戏")

    async def _is_home_203_dominant(self) -> bool:
        """当前帧是否仍为 Xbox 主页 scene203（高置信度）。"""
        if not self._scene_detector or not self._frame_getter:
            return False
        frame = await self._frame_getter()
        if frame is None:
            return False
        image = frame.data if hasattr(frame, "data") else frame
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

    async def _launch_fc_from_home_tile(self) -> bool:
        """在主页 FC 磁贴获焦后按 A 启动，仍停 203 则重试。"""
        for attempt in range(1, FC_LAUNCH_203_MAX_ATTEMPTS + 1):
            if await self._detect_any_scene(list(FC_UT_TARGET_SCENES), strict=False):
                return True

            if not await self._is_fc_tile_focused():
                self.logger.info("启动 FC 前确认磁贴焦点")
                await self._navigate_to_fc_tile_on_home()

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
        image = frame.data if hasattr(frame, 'data') else frame
        if self._scene_detector:
            return self._scene_detector._normalize_frame(image, 203)
        import cv2
        return cv2.resize(image, (960, 540), interpolation=cv2.INTER_AREA)

    async def _green_ratio_in_region(
        self, region: Tuple[int, int, int, int], *, min_ratio: float = 0.04
    ) -> bool:
        """检测 960x540 坐标系内 Xbox 绿框焦点（streaming 风格区域探针）。"""
        import cv2
        import numpy as np

        norm = await self._get_normalized_frame()
        if norm is None:
            return False
        left, top, right, bottom = region
        crop = norm[top:bottom, left:right]
        if crop.size == 0:
            return False
        hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, (35, 80, 80), (85, 255, 255))
        ratio = float(mask.mean()) / 255.0
        return ratio >= min_ratio

    async def _is_top_settings_focused(self) -> bool:
        return await self._green_ratio_in_region((518, 32, 582, 82), min_ratio=0.08)

    async def _is_fc_tile_focused(self) -> bool:
        return await self._green_ratio_in_region((14, 396, 38, 484), min_ratio=0.05)

    def _scene_match_threshold(self, scene_id: int) -> float:
        """Xbox 系统 UI / 小键盘场景允许略低于 schema 默认阈值的匹配。"""
        if scene_id <= 64:
            return 0.60
        if scene_id in FC_UT_TARGET_SCENES:
            # 126/127 在 Xbox 主页有误匹配（~0.76），提高阈值
            return 0.85
        if scene_id == 203:
            return 0.90
        return getattr(self._scene_detector, 'default_threshold', 0.8)

    async def _wait_for_scene(self, scene_id: int, timeout: float = 20.0) -> bool:
        return await self._wait_for_any_scene([scene_id], timeout=timeout)

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

        等待期间：FC/UT 场景每 5s 按 A 跳过弹窗；每 8s 检测 input 通道并发送 keepalive。
        strict=True 时会额外比对 XBOX_UI_AMBIGUOUS_SCENES 以降低误匹配。
        """
        if not self._scene_detector or not self._frame_getter:
            self.logger.warning(f"跳过场景校验 {scene_ids}（未绑定检测器或截帧）")
            return True

        deadline = time.time() + timeout
        last_keepalive = 0.0
        last_skip_press = 0.0
        fc_wait = bool(set(scene_ids) & FC_UT_TARGET_SCENES)
        while time.time() < deadline:
            matched = await self._detect_any_scene(
                scene_ids,
                strict=strict,
                threshold_override=threshold_override,
            )
            if matched is not None:
                self.logger.info(f"场景{matched}校验通过")
                return True
            now = time.time()
            if fc_wait and now - last_skip_press >= 5.0:
                await self._press_button('A', duration=0.12)
                last_skip_press = now
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
        image = frame.data if hasattr(frame, 'data') else frame

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
        return best_id

    async def _log_scene_probe(self, scene_ids: List[int]) -> None:
        """场景校验失败时输出候选场景置信度，便于联调。"""
        if not self._scene_detector or not self._frame_getter:
            return
        frame = await self._frame_getter()
        if frame is None:
            self.logger.warning("场景探针：当前帧为空")
            return
        image = frame.data if hasattr(frame, 'data') else frame
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
            image = frame.data if hasattr(frame, 'data') else frame
            os.makedirs("logs", exist_ok=True)
            path = os.path.join("logs", f"debug_scene{scene_id}_{int(time.time())}.png")
            cv2.imwrite(path, image)
            self.logger.warning(f"已保存场景{scene_id}调试帧: {path}")
        except Exception as e:
            self.logger.debug(f"保存调试帧失败: {e}")

    def _resolve_input_session(self):
        """从串流绑定或动作执行器解析 WebRTC/SmartGlass 会话。"""
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
        image = frame.data if hasattr(frame, "data") else frame
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
        """打开西瓜引导页（场景2），优先使用 scene_transitions 标准按键。"""
        if await self._wait_for_guide(timeout=2.0):
            return True

        on_home = await self._detect_any_scene([203, 1, 24], strict=False)
        openers = []
        if on_home in XBOX_HOME_SCENES:
            openers.append(("NEXUS-from-home", self._press_guide_button))
        openers.extend(
            (
                ("scene_transition 1/1", lambda: self._run_scene_transition(1, 1)),
                ("NEXUS", self._press_guide_button),
            )
        )
        for label, opener in openers:
            self.logger.info(f"尝试打开引导页: {label}")
            await opener()
            if await self._wait_for_guide(timeout=8.0):
                return True

        return False

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

    async def _select_add_switch(self):
        """场景3：优先直接 A（「添加和切换」已高亮时），否则 DOWN 后 A。"""
        if await self._wait_for_scene(5, timeout=2.5):
            return

        await self._press_button('A', duration=0.08)
        if await self._wait_for_scene(5, timeout=3.0):
            return

        for _ in range(2):
            await self._press_button('DPAD_DOWN', duration=0.1)
            await asyncio.sleep(0.2)
        await self._press_button('A', duration=0.1)
        await asyncio.sleep(1.5)

    async def _enter_account_selection(self):
        await self._press_button('A', duration=0.1)
        await asyncio.sleep(1.5)

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

        await self._enter_account_selection()
        if not await self._wait_for_scene(6, timeout=12.0):
            self.logger.warning("读取主机昵称：未能进入场景6")
            await self._save_debug_frame(6)
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

            from ..xbox.stream_keepalive import StreamKeepaliveLoop

            async with StreamKeepaliveLoop(lambda: self._stream_session):
                await self._ensure_input_ready()
                if not await self._open_guide_menu():
                    await self._navigate_to_accounts_system()
                elif not await self._run_scene_transition(2, 2):
                    await self._navigate_to_accounts_system()

                if not await self._wait_for_scene(3):
                    raise RuntimeError("未进入档案和系统页面（场景3）")

                await self._select_add_switch()
                if not await self._wait_for_scene(5, timeout=15.0):
                    raise RuntimeError("未进入添加和切换页面（场景5）")

                await self._select_add_new_user()
                await self._login_with_credentials(email, password)
                host_tag = await self._read_host_gamertag_from_profile_list()
                if account_id and host_tag:
                    stub = GameAccount(
                        account_id=account_id,
                        gamertag=host_tag,
                        email=email,
                    )
                    await self._persist_profile_bound(
                        stub, host_gamertag=host_tag
                    )

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
        """场景5 滚到底部选中「添加新用户」。"""
        self.logger.info("选择「添加新用户」")
        for i in range(12):
            await self._press_button('DPAD_DOWN', duration=0.1)
            await asyncio.sleep(0.18)
        await self._press_button('A', duration=0.1)
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
        image = frame.data if hasattr(frame, 'data') else frame
        if self._scene_detector and hasattr(self._scene_detector, '_normalize_frame'):
            image = self._scene_detector._normalize_frame(image, 6)
        return read_focused_gamertag(image)

    async def _select_account_by_gamertag(
        self,
        gamertag: str,
        *,
        max_slots: int = MAX_PROFILE_LIST_SLOTS,
    ) -> int:
        """
        在场景6列表中按 gamertag 查找档案（不依赖静态 position_index）。

        返回匹配到的列表索引（0=最上方）。
        """
        from ..vision.profile_name_reader import (
            gamertag_matches,
            read_list_gamertags,
        )

        if not gamertag:
            raise RuntimeError("目标 gamertag 为空，无法定位档案")

        await self._scroll_profile_list_to_top()
        await asyncio.sleep(0.35)

        for slot in range(max_slots):
            detected = await self._read_focused_gamertag_from_frame()
            if gamertag_matches(detected, gamertag):
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
                    image = frame.data if hasattr(frame, 'data') else frame
                    if self._scene_detector and hasattr(
                        self._scene_detector, '_normalize_frame'
                    ):
                        image = self._scene_detector._normalize_frame(image, 6)
                    for line in read_list_gamertags(image):
                        if gamertag_matches(line, gamertag):
                            self.logger.info(
                                "场景6列表 OCR 匹配档案 %s（索引 %s，OCR=%r）",
                                gamertag,
                                slot,
                                line,
                            )
                            return slot

            if slot < max_slots - 1:
                await self._press_button('DPAD_DOWN', duration=0.1)
                await asyncio.sleep(0.35)

        await self._save_debug_frame(6)
        raise RuntimeError(
            f"场景6未找到档案 gamertag={gamertag}（已扫描 {max_slots} 行）"
        )

    async def _confirm_account_selection(self):
        await self._press_button('A', duration=0.1)
        await asyncio.sleep(2.0)

    async def _recover_input_if_closed(self) -> bool:
        """input closed 时触发重连，并等待通道 open 后再继续。"""
        from ..xbox.stream_keepalive import (
            ensure_input_channel,
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
            await send_keepalive(self._stream_session)
            return True

        if self._reconnect_callback is not None:
            channel_state = get_input_channel_state(self._stream_session)
            self.logger.warning(
                "input DataChannel 不可用 (state=%s)，尝试重连...",
                channel_state,
            )
            if await self._reconnect_callback():
                ok = await ensure_input_channel(self._stream_session, timeout=8.0)
                if ok:
                    await send_keepalive(self._stream_session)
                    self.logger.info("input 通道重连成功，已恢复 open")
                    ctx = getattr(self, "_task_context", None)
                    if ctx is not None:
                        ctx._input_channel_dirty = False
                    return True
                self.logger.error("重连后会话仍未 open")

        ok = await ensure_input_channel(self._stream_session, timeout=8.0)
        if not ok:
            self.logger.warning(
                "input DataChannel 未就绪: %s",
                get_input_channel_state(self._stream_session),
            )
        elif is_input_channel_open(self._stream_session):
            await send_keepalive(self._stream_session)
        return ok

    async def _ensure_input_ready(self) -> bool:
        return await self._recover_input_if_closed()

    async def _send_keepalive(self) -> None:
        from ..xbox.stream_keepalive import send_keepalive
        if self._stream_session is not None:
            await send_keepalive(self._stream_session)

    async def _login_with_credentials(self, email: str, password: str):
        """微软账号登录：场景10 + 小键盘输入。"""
        from .on_screen_keyboard import OnScreenKeyboard
        from ..xbox.stream_keepalive import StreamKeepaliveLoop

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

        async with StreamKeepaliveLoop(lambda: self._stream_session):
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
        if self._input_gate is not None and not self._input_gate.is_allowed():
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
            active_session = self._resolve_input_session()
            if active_session is None:
                return False
            try:
                if hasattr(active_session, 'send_gamepad_state'):
                    ok_press = await active_session.send_gamepad_state(press.to_dict())
                    await asyncio.sleep(max(duration_sec, 0.05))
                    ok_release = await active_session.send_gamepad_state(release.to_dict())
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
