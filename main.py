# -*- coding: utf-8 -*-
"""
wuwa-auto-player — 自动演奏软件入口。

功能：拖入 MIDI/JSON 生成曲谱，映射到电脑键盘（QWE/ASD/ZXC 三行），
     后台模拟按键在游戏内自动演奏。

依赖：pip install -r requirements.txt
提示：建议以管理员权限运行，以保证游戏能正确识别全局模拟按键。
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication, QMessageBox

from player_engine import PlayerEngine
from score_store import ScoreStore
from ui_float_ball import FloatBall


def _is_admin() -> bool:
    """检测是否以管理员权限运行（Windows）。"""
    try:
        import ctypes
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:  # noqa: BLE001
        return True  # 非 Windows 环境不强制要求


def _setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def main() -> int:
    _setup_logging()
    logger = logging.getLogger("WuwaAutoPlayer")

    app = QApplication(sys.argv)
    app.setApplicationName("wuwa-auto-player")
    app.setQuitOnLastWindowClosed(False)  # 关闭预览窗口后悬浮球仍驻留

    # 打包成 exe 后，数据目录放在 exe 同级，保证曲谱库可持久化
    if getattr(sys, "frozen", False):
        base_dir = Path(sys.executable).resolve().parent
    else:
        base_dir = Path(__file__).resolve().parent

    store = ScoreStore(base_dir / "scores")
    # 古筝等有余音乐器：松键不影响余音，采用“点按”（按下约 0.08s 即松开），
    # 避免按住过久导致同键重叠卡音；如需按曲谱时值按住，将 hold_sec 改为 None。
    engine = PlayerEngine(start_delay=3.0, hold_sec=0.08)

    ball = FloatBall(store, engine)
    ball.show_at_top_right()

    if not _is_admin():
        logger.warning("当前未以管理员权限运行")
        QMessageBox.warning(
            None,
            "权限提示",
            "检测到当前未以管理员权限运行。\n\n"
            "部分游戏对底层模拟按键有权限要求，\n"
            "建议右键以“管理员身份运行”本程序，\n"
            "以确保游戏内能正确识别演奏按键。",
        )

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
