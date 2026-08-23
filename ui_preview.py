# -*- coding: utf-8 -*-
"""可视化曲谱预览窗口：钢琴卷帘窗（Piano Roll）。"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import (
    QColor, QFont, QPainter, QPainterPath, QPen, QBrush,
)
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QScrollArea, QVBoxLayout, QWidget,
)

from key_mapping import ORDERED_PITCHES, NOTE_TO_KEY, KEY_TO_NOTE, MIN_PITCH, MAX_PITCH
from score_model import Score


class PianoRollWidget(QWidget):
    """自绘钢琴卷帘：横向为时间，纵向为音高（键）。"""

    PX_PER_SEC = 140  # 每秒对应像素宽度
    ROW_HEIGHT = 26   # 每行（每个键）高度
    LEFT_MARGIN = 64  # 左侧键名标签宽度
    TOP_MARGIN = 8

    # 中央 C 及每八度 C 用于加深分隔
    _C_PITCHES = {48, 60, 72}

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._score: Optional[Score] = None
        self._max_time = 1.0
        self.setMinimumHeight(TOP_MARGIN * 2 + len(ORDERED_PITCHES) * self.ROW_HEIGHT)

    def set_score(self, score: Score) -> None:
        self._score = score
        self._max_time = 1.0
        for n in score.notes:
            self._max_time = max(self._max_time, n.start_sec + n.duration_sec)
        width = int(self.LEFT_MARGIN + self._max_time * self.PX_PER_SEC + 40)
        self.setMinimumWidth(width)
        self.resize(width, self.minimumHeight())
        self.update()

    # ---------- 绘制 ----------
    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        n_rows = len(ORDERED_PITCHES)
        content_w = int(self.LEFT_MARGIN + self._max_time * self.PX_PER_SEC + 20)

        # 背景
        painter.fillRect(self.rect(), QColor(30, 32, 42))

        # 行背景（白键）+ 键名标签
        for row, pitch in enumerate(ORDERED_PITCHES):
            # 从下往上：最低音在底部
            y = self.TOP_MARGIN + (n_rows - 1 - row) * self.ROW_HEIGHT
            rect = QRectF(self.LEFT_MARGIN, y, content_w - self.LEFT_MARGIN, self.ROW_HEIGHT - 1)

            is_c = pitch in self._C_PITCHES
            base = QColor(52, 54, 66) if not is_c else QColor(58, 60, 74)
            painter.fillRect(rect, base)

            # 键名标签
            painter.setPen(QColor(210, 212, 220))
            font = QFont("Consolas", 9, QFont.Bold)
            painter.setFont(font)
            painter.drawText(
                QRectF(6, y, self.LEFT_MARGIN - 10, self.ROW_HEIGHT),
                Qt.AlignRight | Qt.AlignVCenter,
                NOTE_TO_KEY[pitch],
            )

        # 时间网格线（每秒）
        painter.setPen(QPen(QColor(70, 72, 86), 1))
        seconds = int(self._max_time) + 1
        for s in range(seconds + 1):
            x = self.LEFT_MARGIN + s * self.PX_PER_SEC
            painter.drawLine(int(x), self.TOP_MARGIN, int(x), self.TOP_MARGIN + n_rows * self.ROW_HEIGHT)

        # 音符矩形
        if self._score:
            painter.setPen(Qt.NoPen)
            for n in self._score.notes:
                try:
                    row = ORDERED_PITCHES.index(KEY_TO_NOTE[n.key])
                except (KeyError, ValueError):
                    continue
                y = self.TOP_MARGIN + (n_rows - 1 - row) * self.ROW_HEIGHT + 2
                x = self.LEFT_MARGIN + n.start_sec * self.PX_PER_SEC
                w = max(4.0, n.duration_sec * self.PX_PER_SEC - 1)
                h = self.ROW_HEIGHT - 5
                note_rect = QRectF(x, y, w, h)

                gradient = QColor(72, 200, 160)
                painter.setBrush(QBrush(gradient))
                painter.drawRoundedRect(note_rect, 3, 3)

        painter.end()


class PreviewWindow(QFrame):
    """半透明（近似毛玻璃）的预览悬浮窗。"""

    def __init__(self, score: Optional[Score] = None):
        super().__init__()
        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setWindowOpacity(0.94)

        self._roll = PianoRollWidget()
        scroll = QScrollArea()
        scroll.setWidget(self._roll)
        scroll.setWidgetResizable(False)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setFrameShape(QFrame.NoFrame)

        # 顶部信息栏
        title_label = QLabel("曲谱预览")
        title_label.setStyleSheet(
            "color:#eee;font-size:15px;font-weight:bold;padding:4px 8px;"
        )
        self._info_label = QLabel("")
        self._info_label.setStyleSheet("color:#aaa;font-size:11px;padding:2px 8px;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(title_label)
        layout.addWidget(self._info_label)
        layout.addWidget(scroll)

        # 圆角深色背景 + 阴影（近似毛玻璃）
        self.setStyleSheet(
            "PreviewWindow {"
            "  background-color: rgba(24, 26, 34, 235);"
            "  border-radius: 12px;"
            "  border: 1px solid rgba(255,255,255,40);"
            "}"
        )

        self.resize(760, 520)
        if score is not None:
            self.set_score(score)

    def set_score(self, score: Score) -> None:
        self._roll.set_score(score)
        self._info_label.setText(
            f"《{score.title}》  BPM {score.bpm}   音符 {len(score.notes)} 个"
        )
        self.setWindowTitle(f"曲谱预览 - {score.title}")

    def mousePressEvent(self, event) -> None:  # noqa: N802
        """按住空白处可拖动窗口。"""
        if event.button() == Qt.LeftButton:
            self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if event.buttons() & Qt.LeftButton and hasattr(self, "_drag_offset"):
            self.move(event.globalPosition().toPoint() - self._drag_offset)
            event.accept()
