# -*- coding: utf-8 -*-
"""
管理员权限下的原生文件拖放支持（绕过 Windows UIPI 隔离）。

原理：Qt 默认使用 OLE 拖放，管理员权限下普通权限的资源管理器无法向其投递，
单纯放行 WM_DROPFILES 无效。这里撤销 Qt 的 OLE drop target，回退到
WM_DROPFILES 原生机制，并通过 ChangeWindowMessageFilterEx 放行该消息。
"""
from __future__ import annotations

import ctypes
import logging
import sys
from ctypes import wintypes
from typing import Callable, List, Optional

from PySide6.QtCore import QAbstractNativeEventFilter

logger = logging.getLogger("WuwaAutoPlayer")

WM_DROPFILES = 0x0233
WM_COPYDATA = 0x004A
WM_COPYGLOBALDATA = 0x0049
MSGFLT_ALLOW = 1


def is_admin() -> bool:
    """检测是否以管理员权限运行（Windows）。"""
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:  # noqa: BLE001
        return False


def _query_drop_files(hdrop) -> List[str]:
    """从 HDROP 句柄中提取被拖入的文件路径列表，并释放资源。"""
    shell32 = ctypes.windll.shell32
    shell32.DragQueryFileW.argtypes = [
        wintypes.HANDLE, wintypes.UINT, wintypes.LPWSTR, wintypes.UINT,
    ]
    shell32.DragQueryFileW.restype = wintypes.UINT
    shell32.DragFinish.argtypes = [wintypes.HANDLE]
    shell32.DragFinish.restype = None

    hdrop = int(hdrop)
    count = shell32.DragQueryFileW(hdrop, 0xFFFFFFFF, None, 0)
    files: List[str] = []
    for i in range(count):
        buf = ctypes.create_unicode_buffer(1024)
        shell32.DragQueryFileW(hdrop, i, buf, 1024)
        files.append(buf.value)
    shell32.DragFinish(hdrop)
    return files


class NativeDropFilter(QAbstractNativeEventFilter):
    """捕获 WM_DROPFILES 并回调文件路径。"""

    def __init__(self, on_files: Callable[[str], None]):
        super().__init__()
        self.on_files = on_files

    def nativeEventFilter(self, event_type, message):
        try:
            if event_type not in (b"windows_generic_MSG", b"windows_dispatcher_MSG"):
                return False, 0
            msg = ctypes.cast(int(message), ctypes.POINTER(wintypes.MSG)).contents
            if msg.message == WM_DROPFILES:
                for f in _query_drop_files(msg.wParam):
                    self.on_files(f)
                return True, 0
        except Exception as exc:  # noqa: BLE001
            logger.warning("原生拖放处理异常：%s", exc)
        return False, 0


def enable_admin_drop(hwnd: int, on_files: Callable[[str], None]) -> Optional[NativeDropFilter]:
    """
    在管理员权限下启用原生文件拖放。返回需要被安装并保持引用的过滤器；
    非管理员、非 Windows 或无效窗口句柄时返回 None。
    """
    if sys.platform != "win32" or not hwnd or not is_admin():
        return None
    try:
        user32 = ctypes.windll.user32
        shell32 = ctypes.windll.shell32
        ole32 = ctypes.windll.ole32

        user32.ChangeWindowMessageFilterEx.restype = wintypes.BOOL
        user32.ChangeWindowMessageFilterEx.argtypes = [
            wintypes.HWND, wintypes.UINT, wintypes.DWORD, ctypes.c_void_p,
        ]
        for msg in (WM_DROPFILES, WM_COPYDATA, WM_COPYGLOBALDATA):
            user32.ChangeWindowMessageFilterEx(hwnd, msg, MSGFLT_ALLOW, None)

        # 接受 shell 拖放（WM_DROPFILES）
        shell32.DragAcceptFiles(hwnd, True)

        # 撤销 Qt 注册的 OLE drop target，回退到 WM_DROPFILES
        try:
            ole32.RevokeDragDrop(hwnd)
        except Exception:  # noqa: BLE001
            pass

        logger.info("已启用管理员权限下的原生文件拖放")
        return NativeDropFilter(on_files)
    except Exception as exc:  # noqa: BLE001
        logger.warning("启用管理员拖放失败：%s", exc)
        return None
