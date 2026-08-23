# -*- coding: utf-8 -*-
"""自动演奏引擎：使用 pynput 精确模拟按键按下与释放。"""
from __future__ import annotations

import logging
import threading
import time
from collections import defaultdict
from typing import Callable, List, Optional, Tuple

from score_model import Score, Note

logger = logging.getLogger("WuwaAutoPlayer")

try:
    from pynput.keyboard import Controller
    _HAS_PYNPUT = True
except Exception:  # noqa: BLE001
    _HAS_PYNPUT = False

# 状态常量
STATE_IDLE = "idle"
STATE_PLAYING = "playing"
STATE_PAUSED = "paused"
STATE_FINISHED = "finished"
STATE_STOPPED = "stopped"


def detect_overlaps(notes: List[Note], hold_sec: Optional[float] = None) -> List[str]:
    """
    检测同一键在时间上重叠（前一键尚未释放又被按下）的冲突，
    用于提示可能导致的“卡音”。
    """
    warnings: List[str] = []
    by_key: dict[str, List[Tuple[float, float]]] = defaultdict(list)
    for n in notes:
        hold = n.duration_sec if hold_sec is None else hold_sec
        by_key[n.key].append((n.start_sec, n.start_sec + hold))

    for key, intervals in by_key.items():
        intervals.sort()
        for i in range(len(intervals) - 1):
            cur_end = intervals[i][1]
            nxt_start = intervals[i + 1][0]
            if nxt_start < cur_end:
                warnings.append(
                    f"键 {key}：{intervals[i]} 与 {intervals[i + 1]} 时间重叠，可能卡音"
                )
    return warnings


class PlayerEngine:
    """后台线程驱动、支持开始/暂停/恢复/停止的自动演奏引擎。"""

    def __init__(self, start_delay: float = 3.0, hold_sec: Optional[float] = None,
                 gap_ms: float = 0.0):
        self.start_delay = max(0.0, start_delay)
        # hold_sec：按键按住时长（秒）。None = 按曲谱 duration_sec 按住（钢琴等止音乐器）；
        # 设为较小正数 = “点按”（古筝等有余音乐器，松键不影响余音，快速松开避免卡音）。
        self.hold_sec = hold_sec
        # gap_ms：相邻两个按键之间的最小间隔（毫秒），用于拉开过密音符，避免漏判。
        self.gap_ms = max(0.0, float(gap_ms))
        self._keyboard: Optional[Controller] = Controller() if _HAS_PYNPUT else None
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._pause_event = threading.Event()
        self._score: Optional[Score] = None

        # 状态回调：on_state(state, message)
        self.on_state: Optional[Callable[[str, str], None]] = None

        # 当前已按下但未释放的键集合
        self._pressed: set[str] = set()

    # ---------- 对外接口 ----------
    def load(self, score: Score) -> None:
        self._score = score

    @property
    def score(self) -> Optional[Score]:
        return self._score

    @property
    def state(self) -> str:
        if self._thread and self._thread.is_alive():
            return STATE_PAUSED if self._pause_event.is_set() else STATE_PLAYING
        return STATE_IDLE

    def start(self, score: Optional[Score] = None) -> bool:
        """开始演奏；若已在线程中则忽略。"""
        if not _HAS_PYNPUT:
            self._emit(STATE_IDLE, "未安装 pynput，无法模拟按键（pip install pynput）")
            return False
        if score is not None:
            self._score = score
        if self._score is None or not self._score.notes:
            self._emit(STATE_IDLE, "无可演奏的曲谱")
            return False
        if self._thread and self._thread.is_alive():
            logger.warning("演奏已在进行中，忽略重复启动")
            return False

        self._stop_event.clear()
        self._pause_event.clear()
        self._pressed.clear()
        self._thread = threading.Thread(target=self._run, name="PlayerEngine", daemon=True)
        self._thread.start()
        return True

    def pause(self) -> None:
        self._pause_event.set()

    def resume(self) -> None:
        self._pause_event.clear()

    def toggle_pause(self) -> None:
        if self._pause_event.is_set():
            self.resume()
        else:
            self.pause()

    def stop(self) -> None:
        self._stop_event.set()
        self._pause_event.clear()  # 解除暂停，让线程退出
        self._release_all()

    # ---------- 内部实现 ----------
    def _emit(self, state: str, message: str = "") -> None:
        if self.on_state:
            try:
                self.on_state(state, message)
            except Exception as exc:  # noqa: BLE001
                logger.warning("状态回调异常：%s", exc)

    def _press(self, key: str) -> None:
        if self._keyboard is None:
            return
        physical = key.lower()
        try:
            self._keyboard.press(physical)
            self._pressed.add(physical)
        except Exception as exc:  # noqa: BLE001
            logger.warning("按下键 %s 失败：%s", physical, exc)

    def _release(self, key: str) -> None:
        if self._keyboard is None:
            return
        physical = key.lower()
        try:
            self._keyboard.release(physical)
        except Exception as exc:  # noqa: BLE001
            logger.warning("释放键 %s 失败：%s", physical, exc)
        finally:
            self._pressed.discard(physical)

    def _release_all(self) -> None:
        if self._keyboard is None:
            return
        for physical in list(self._pressed):
            try:
                self._keyboard.release(physical)
            except Exception as exc:  # noqa: BLE001
                logger.warning("释放键 %s 失败：%s", physical, exc)
        self._pressed.clear()

    def _build_events(self, notes: Optional[List[Note]] = None) -> List[Tuple[float, int, str]]:
        """构建 (时间, 类型, 键) 事件列表，类型 0=按下 1=释放。"""
        if notes is None:
            notes = self._score.notes
        events: List[Tuple[float, int, str]] = []
        hold_sec = self.hold_sec
        for n in notes:
            hold = n.duration_sec if hold_sec is None else hold_sec
            events.append((n.start_sec, 0, n.key))
            events.append((n.start_sec + hold, 1, n.key))
        # 同一时刻先处理“释放”再处理“按下”，避免同键瞬间卡音
        events.sort(key=lambda e: (e[0], e[1], e[2]))
        return events

    def _apply_gap(self, notes: List[Note]) -> List[Note]:
        """按 gap_ms 拉开相邻音符：保证相邻按下时间至少间隔 gap_ms 毫秒。"""
        gap = self.gap_ms / 1000.0
        if gap <= 0:
            return notes
        ordered = sorted(notes, key=lambda n: (n.start_sec, n.key))
        adjusted: List[Note] = []
        last_start: Optional[float] = None
        for n in ordered:
            if last_start is None:
                new_start = n.start_sec
            else:
                new_start = max(n.start_sec, last_start + gap)
            adjusted.append(Note(
                key=n.key,
                start_sec=round(new_start, 4),
                duration_sec=n.duration_sec,
            ))
            last_start = new_start
        return adjusted

    def _run(self) -> None:
        score = self._score
        if score is None:
            return

        # 应用按键间隔，并做冲突检测（仅记录，不中断）
        notes = self._apply_gap(score.notes)
        overlaps = detect_overlaps(notes, self.hold_sec)
        for w in overlaps:
            logger.warning("按键冲突：%s", w)

        events = self._build_events(notes)
        total = len(events)

        # 启动延迟（给用户时间切回游戏窗口）
        if self.start_delay > 0:
            self._emit(STATE_PLAYING, f"将在 {self.start_delay:.0f} 秒后开始，请切回游戏窗口…")
            delay_end = time.perf_counter() + self.start_delay
            while time.perf_counter() < delay_end:
                if self._stop_event.is_set():
                    self._emit(STATE_STOPPED, "演奏已停止")
                    return
                time.sleep(0.02)

        start = time.perf_counter()
        idx = 0
        self._emit(STATE_PLAYING, f"开始演奏《{score.title}》，共 {len(score.notes)} 个音符")

        while idx < total and not self._stop_event.is_set():
            # 暂停：阻塞并补偿时间
            if self._pause_event.is_set():
                self._emit(STATE_PAUSED, "演奏已暂停")
                paused_at = time.perf_counter()
                while self._pause_event.is_set() and not self._stop_event.is_set():
                    time.sleep(0.05)
                if self._stop_event.is_set():
                    break
                start += time.perf_counter() - paused_at
                self._emit(STATE_PLAYING, "演奏已恢复")

            t, etype, key = events[idx]
            now = time.perf_counter() - start
            if now >= t:
                if etype == 0:
                    self._press(key)
                else:
                    self._release(key)
                idx += 1
            else:
                time.sleep(min(0.01, t - now))

        self._release_all()

        if self._stop_event.is_set():
            self._emit(STATE_STOPPED, "演奏已停止")
        else:
            self._emit(STATE_FINISHED, f"《{score.title}》演奏完成")
