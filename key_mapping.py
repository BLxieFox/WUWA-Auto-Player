# -*- coding: utf-8 -*-
"""
键盘与音高映射模块。

三组八度映射（中间不得空缺）：
    低音区(第3八度): Z=C3  X=D3  C=E3  V=F3  B=G3  N=A3  M=B3
    中音区(第4八度): A=C4  S=D4  D=E4  F=F4  G=G4  H=A4  J=B4
    高音区(第5八度): Q=C5  W=D5  E=E5  R=F5  T=G5  Y=A5  U=B5

注意：此处使用 MIDI 音高编号（C3=48, C4=60, C5=72）。
"""
from __future__ import annotations

import logging

logger = logging.getLogger("WuwaAutoPlayer")

# MIDI 音高编号 -> 键盘键名（大写字母）
NOTE_TO_KEY: dict[int, str] = {
    48: "Z",  # C3
    50: "X",  # D3
    52: "C",  # E3
    53: "V",  # F3
    55: "B",  # G3
    57: "N",  # A3
    59: "M",  # B3
    60: "A",  # C4（中央C）
    62: "S",  # D4
    64: "D",  # E4
    65: "F",  # F4
    67: "G",  # G4
    69: "H",  # A4
    71: "J",  # B4
    72: "Q",  # C5
    74: "W",  # D5
    76: "E",  # E5
    77: "R",  # F5
    79: "T",  # G5
    81: "Y",  # A5
    83: "U",  # B5
}

# 键盘键名 -> MIDI 音高编号
KEY_TO_NOTE: dict[str, int] = {v: k for k, v in NOTE_TO_KEY.items()}

# 可演奏音高范围（闭区间）
MIN_PITCH: int = min(NOTE_TO_KEY)
MAX_PITCH: int = max(NOTE_TO_KEY)

# 升序排列的音高列表（用于钢琴卷帘纵向排布）
ORDERED_PITCHES: list[int] = sorted(NOTE_TO_KEY)

# 合法键名集合
VALID_KEYS: frozenset[str] = frozenset(NOTE_TO_KEY.values())


def _validate_mapping() -> bool:
    """校验映射为单射且无冲突（每个音高对应唯一键、每个键对应唯一音高）。"""
    if len(NOTE_TO_KEY) != len(KEY_TO_NOTE):
        logger.error("键盘映射冲突：键/音高并非一一对应！")
        return False
    # 检查是否覆盖 C3~B5 之间的自然音（全白键）
    expected = [48, 50, 52, 53, 55, 57, 59,
                60, 62, 64, 65, 67, 69, 71,
                72, 74, 76, 77, 79, 81, 83]
    if sorted(NOTE_TO_KEY) != expected:
        logger.warning("映射表与预期的三个八度自然音不完全一致，请检查。")
    return True


def pitch_to_key(midi_pitch) -> str:
    """
    将 MIDI 音高映射到键盘键。

    超出 [MIN_PITCH, MAX_PITCH] 范围的音符，先通过 ±12（移八度）就近调整回可演奏区间；
    落在黑键（半音）上的音符，就近映射到相邻的最近白键。两种情况均记录警告日志。
    """
    try:
        p = int(round(float(midi_pitch)))
    except (TypeError, ValueError):
        logger.warning("无法解析的音高值 %r，按中央 C（键 A）处理", midi_pitch)
        p = 60

    if p < MIN_PITCH or p > MAX_PITCH:
        logger.warning(
            "音高 %d 超出可演奏范围 [%d, %d]，按八度就近调整",
            p, MIN_PITCH, MAX_PITCH,
        )
        while p < MIN_PITCH:
            p += 12
        while p > MAX_PITCH:
            p -= 12

    if p in NOTE_TO_KEY:
        return NOTE_TO_KEY[p]

    # 黑键（半音）：就近取最近的可演奏白键
    nearest = min(ORDERED_PITCHES, key=lambda x: abs(x - p))
    logger.warning(
        "音高 %d 为半音（黑键），就近映射到 %d（键 %s）",
        p, nearest, NOTE_TO_KEY[nearest],
    )
    return NOTE_TO_KEY[nearest]


_validate_mapping()
