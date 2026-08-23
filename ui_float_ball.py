# -*- coding: utf-8 -*-
"""悬浮球交互 UI：圆形置顶小球，支持拖动、单击菜单、双击预览、拖拽导入。"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, QTimer, Signal, QPoint
from PySide6.QtGui import (
    QAction, QColor, QFont, QPainter, QPainterPath, QRadialGradient, QBrush,
)
from PySide6.QtWidgets import (
    QApplication, QMenu, QMessageBox, QFileDialog, QInputDialog, QWidget,
)

from midi_parser import parse_midi, MidiParseError
from player_engine import (
    PlayerEngine, STATE_PLAYING, STATE_PAUSED, STATE_IDLE,
)
from score_model import Score, validate_score
from score_store import ScoreStore
from ui_preview import PreviewWindow
from win_admin_drop import enable_admin_drop

logger = logging.getLogger("WuwaAutoPlayer")

BALL_SIZE = 68
DRAG_THRESHOLD = 6  # 像素位移阈值，用于区分单击与拖动


class FloatBall(QWidget):
    """悬浮球主控件。"""

    # 引擎状态信号（跨线程安全转发到主线程）
    state_changed = Signal(str, str)

    def __init__(self, store: ScoreStore, engine: PlayerEngine):
        super().__init__()
        self.store = store
        self.engine = engine
        self.current_score: Optional[Score] = None
        self.preview: Optional[PreviewWindow] = None
        self._status_text = "琴"

        # 无边框 + 置顶 + 不显示在任务栏
        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setFixedSize(BALL_SIZE, BALL_SIZE)
        self.setAcceptDrops(True)
        self.setToolTip("拖入 .mid/.json 导入曲谱\n单击=曲谱库  双击=预览  右键=菜单")

        # 拖动状态
        self._drag_active = False
        self._press_global: Optional[QPoint] = None
        self._press_window_pos: Optional[QPoint] = None

        # 单击延迟定时器（区分单击与双击）
        self._click_timer = QTimer(self)
        self._click_timer.setSingleShot(True)
        self._click_timer.setInterval(260)
        self._click_timer.timeout.connect(self._show_library_menu)

        # 引擎状态回调 -> 转发到主线程
        self.engine.on_state = lambda state, msg: self.state_changed.emit(state, msg)
        self.state_changed.connect(self._on_state_changed)

        # 管理员权限下的原生拖放过滤器（保持引用，避免被回收）
        self._native_drop_filter = None

        # 精简设置（拖入 MIDI 解析时生效）
        self.simplify_chords = True   # 和弦只留最高音
        self.min_duration_ms = 40     # 短音过滤阈值（毫秒），0 表示不过滤

    # ---------- 位置：默认屏幕右上角 ----------
    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        # 管理员权限下启用原生 WM_DROPFILES 拖放；普通权限走 Qt 默认拖放
        if self._native_drop_filter is None:
            QTimer.singleShot(0, self._setup_native_drop)

    def _setup_native_drop(self) -> None:
        drop_filter = enable_admin_drop(int(self.winId()), self._handle_drop)
        if drop_filter is not None:
            QApplication.instance().installNativeEventFilter(drop_filter)
            self._native_drop_filter = drop_filter

    def show_at_top_right(self) -> None:
        screen = self.screen()
        if screen is None:
            self.show()
            return
        geo = screen.availableGeometry()
        x = geo.right() - self.width() - 24
        y = geo.top() + 24
        self.move(x, y)
        self.show()

    # ---------- 绘制 ----------
    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        center = self.rect().center()
        radius = self.width() / 2 - 2

        # 径向渐变球体
        grad = QRadialGradient(center - QPoint(radius * 0.35, radius * 0.4), radius)
        if self.engine.state == STATE_PLAYING:
            grad.setColorAt(0.0, QColor(90, 220, 180))
            grad.setColorAt(1.0, QColor(20, 120, 100))
        elif self.engine.state == STATE_PAUSED:
            grad.setColorAt(0.0, QColor(240, 200, 90))
            grad.setColorAt(1.0, QColor(150, 110, 30))
        else:
            grad.setColorAt(0.0, QColor(110, 140, 220))
            grad.setColorAt(1.0, QColor(40, 60, 130))

        painter.setBrush(QBrush(grad))
        painter.setPen(QColor(255, 255, 255, 70))
        painter.drawEllipse(center, radius, radius)

        # 高光
        painter.setBrush(QColor(255, 255, 255, 60))
        painter.setPen(Qt.NoPen)
        highlight = QPainterPath()
        highlight.addEllipse(center - QPoint(radius * 0.35, radius * 0.45), radius * 0.32, radius * 0.24)
        painter.drawPath(highlight)

        # 中心文字
        painter.setPen(QColor(255, 255, 255, 235))
        font = QFont("Microsoft YaHei", 22, QFont.Bold)
        painter.setFont(font)
        painter.drawText(self.rect(), Qt.AlignCenter, self._status_text)

        painter.end()

    # ---------- 鼠标事件 ----------
    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.LeftButton:
            self._press_global = event.globalPosition().toPoint()
            self._press_window_pos = self.pos()
            self._drag_active = False
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if (event.buttons() & Qt.LeftButton) and self._press_global is not None:
            delta = event.globalPosition().toPoint() - self._press_global
            if not self._drag_active and (
                abs(delta.x()) > DRAG_THRESHOLD or abs(delta.y()) > DRAG_THRESHOLD
            ):
                self._drag_active = True
            if self._drag_active and self._press_window_pos is not None:
                self.move(self._press_window_pos + delta)
                event.accept()
                return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.LeftButton and not self._drag_active:
            # 短按：延迟弹菜单，给双击留出时间
            self._click_timer.start()
            event.accept()
            return
        self._press_global = None
        self._drag_active = False
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.LeftButton:
            self._click_timer.stop()
            self._open_preview()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def contextMenuEvent(self, event) -> None:  # noqa: N802
        """右键菜单。"""
        menu = QMenu(self)
        menu.setStyleSheet("QMenu{background:#222;color:#eee;border:1px solid #444;}"
                           "QMenu::item:selected{background:#3a5aa0;}")

        playing = self.engine.state in (STATE_PLAYING, STATE_PAUSED)

        act_play = menu.addAction("开始演奏" if not playing else "暂停/继续")
        act_play.triggered.connect(self._toggle_play)

        act_export = menu.addAction("导出当前曲谱为 JSON")
        act_export.triggered.connect(self._export_current)

        act_gap = menu.addAction(f"按键间隔：{int(self.engine.gap_ms)} ms")
        act_gap.triggered.connect(self._set_gap)

        # 精简设置子菜单
        sub_simplify = menu.addMenu("精简设置")
        act_simplify = sub_simplify.addAction("和弦精简（只留最高音）")
        act_simplify.setCheckable(True)
        act_simplify.setChecked(self.simplify_chords)
        act_simplify.triggered.connect(self._toggle_simplify_chords)

        act_min_dur = sub_simplify.addAction(f"短音过滤阈值：{self.min_duration_ms} ms")
        act_min_dur.triggered.connect(self._set_min_duration)

        menu.addSeparator()

        act_refresh = menu.addAction("刷新曲谱库")
        act_refresh.triggered.connect(lambda: self._show_library_menu())

        menu.addSeparator()

        act_quit = menu.addAction("退出")
        act_quit.triggered.connect(self._quit)

        menu.exec_(event.globalPos())

    # ---------- 菜单动作 ----------
    def _show_library_menu(self) -> None:
        menu = QMenu(self)
        menu.setStyleSheet("QMenu{background:#222;color:#eee;border:1px solid #444;}"
                           "QMenu::item:selected{background:#3a5aa0;}")

        titles = self.store.list_titles()
        if not titles:
            empty = menu.addAction("（曲谱库为空，请拖入 .mid/.json）")
            empty.setEnabled(False)
        else:
            for t in titles:
                act = menu.addAction(t)
                act.triggered.connect(lambda checked=False, title=t: self._load_score_by_title(title))

        menu.exec_(self._menu_pos())

    def _menu_pos(self) -> QPoint:
        """菜单弹出位置：小球正下方。"""
        return self.mapToGlobal(QPoint(0, self.height() + 4))

    def _load_score_by_title(self, title: str) -> None:
        try:
            score = self.store.load(title)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "加载失败", f"无法加载曲谱 [{title}]：\n{exc}")
            return
        self.current_score = score
        self._status_text = "♪"
        self.update()
        logger.info("已加载曲谱：%s", score.title)
        QMessageBox.information(self, "曲谱已加载",
                                f"《{score.title}》\nBPM {score.bpm}  音符 {len(score.notes)} 个\n右键 → 开始演奏")

    def _open_preview(self) -> None:
        if self.current_score is None:
            QMessageBox.information(self, "提示", "尚未加载曲谱。\n请先从曲谱库加载或拖入 .mid/.json 文件。")
            return
        if self.preview is None:
            self.preview = PreviewWindow()
        self.preview.set_score(self.current_score)
        self.preview.show()
        self.preview.raise_()

    def _toggle_play(self) -> None:
        if self.current_score is None:
            QMessageBox.information(self, "提示", "尚未加载曲谱，无法演奏。")
            return
        if self.engine.state == STATE_IDLE:
            self.engine.load(self.current_score)
            self.engine.start()
        elif self.engine.state in (STATE_PLAYING, STATE_PAUSED):
            # 已开始 -> 停止
            self.engine.stop()

    def _export_current(self) -> None:
        if self.current_score is None:
            QMessageBox.warning(self, "导出失败", "请先加载曲谱。")
            return
        default = f"{self.current_score.title}.json"
        path, _ = QFileDialog.getSaveFileName(
            self, "导出曲谱为 JSON", default, "JSON 文件 (*.json)"
        )
        if not path:
            return
        try:
            if not path.lower().endswith(".json"):
                path += ".json"
            Path(path).write_text(self.current_score.to_json(), encoding="utf-8")
            QMessageBox.information(self, "导出成功", f"曲谱已导出到：\n{path}")
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "导出失败", str(exc))

    def _set_gap(self) -> None:
        """弹窗调节相邻按键之间的间隔（毫秒）。"""
        current = int(self.engine.gap_ms)
        value, ok = QInputDialog.getInt(
            self,
            "按键间隔设置",
            "相邻两个按键之间的间隔（毫秒）：",
            current, 0, 5000, 10,
        )
        if ok:
            self.engine.gap_ms = float(value)
            self.setToolTip(f"wuwa-auto-player — 按键间隔已设为 {value} ms")
            logger.info("按键间隔已设为 %d ms", value)

    def _toggle_simplify_chords(self, checked: bool) -> None:
        """切换和弦精简开关。"""
        self.simplify_chords = bool(checked)
        logger.info("和弦精简：%s", "开启" if checked else "关闭")

    def _set_min_duration(self) -> None:
        """弹窗调节短音过滤阈值（毫秒）。"""
        value, ok = QInputDialog.getInt(
            self,
            "短音过滤阈值",
            "过滤时值短于此毫秒数的音符（0 = 不过滤）：",
            self.min_duration_ms, 0, 5000, 10,
        )
        if ok:
            self.min_duration_ms = value
            logger.info("短音过滤阈值：%d ms", value)

    def _quit(self) -> None:
        self.engine.stop()
        from PySide6.QtWidgets import QApplication
        QApplication.instance().quit()

    # ---------- 拖拽导入 ----------
    def dragEnterEvent(self, event) -> None:  # noqa: N802
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                p = url.toLocalFile().lower()
                if p.endswith((".mid", ".midi", ".json")):
                    event.acceptProposedAction()
                    return
        event.ignore()

    def dragMoveEvent(self, event) -> None:  # noqa: N802
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event) -> None:  # noqa: N802
        for url in event.mimeData().urls():
            self._handle_drop(url.toLocalFile())
        event.acceptProposedAction()

    def _handle_drop(self, path: str) -> None:
        p = Path(path)
        ext = p.suffix.lower()
        if ext == ".json":
            self._import_json(p)
        elif ext in (".mid", ".midi"):
            self._import_midi(p)
        else:
            QMessageBox.warning(self, "不支持的文件", f"无法识别文件类型：{p.name}")

    def _import_midi(self, path: Path) -> None:
        try:
            score = parse_midi(
                path,
                simplify_chords=self.simplify_chords,
                min_duration_sec=self.min_duration_ms / 1000.0,
            )
        except MidiParseError as exc:
            QMessageBox.warning(self, "解析失败", str(exc))
            return
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "解析失败", f"发生未知错误：{exc}")
            return
        try:
            self.store.save(score)
        except Exception as exc:  # noqa: BLE001
            logger.warning("保存曲谱失败：%s", exc)
        self.current_score = score
        self._status_text = "♪"
        self.update()
        QMessageBox.information(
            self, "解析成功",
            f"[{path.name}] 解析成功！\n共提取 {len(score.notes)} 个音符",
        )

    def _import_json(self, path: Path) -> None:
        try:
            score = Score.from_json(path.read_text(encoding="utf-8"))
            ok, errors = validate_score(score)
            if not ok:
                QMessageBox.warning(self, "格式校验失败", "\n".join(errors))
                return
            self.store.save(score)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "导入失败", f"JSON 格式有误：\n{exc}")
            return
        self.current_score = score
        self._status_text = "♪"
        self.update()
        QMessageBox.information(self, "导入成功", f"曲谱 [{score.title}] 导入成功！")

    # ---------- 引擎状态回调（主线程） ----------
    def _on_state_changed(self, state: str, message: str) -> None:
        if state == STATE_PLAYING:
            self._status_text = "▶"
        elif state == STATE_PAUSED:
            self._status_text = "⏸"
        else:
            self._status_text = "琴" if self.current_score is None else "♪"
        self.update()
        if message:
            self.setToolTip(f"wuwa-auto-player — {message}")
            logger.info(message)
