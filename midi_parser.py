# -*- coding: utf-8 -*-
"""MIDI 解析模块：使用 music21 提取音符（音高/开始时间/持续时间）。"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Tuple

from key_mapping import pitch_to_key
from score_model import Score, Note

logger = logging.getLogger("WuwaAutoPlayer")


class MidiParseError(Exception):
    """MIDI 解析失败的统一异常。"""


def _keep_highest_per_onset(
    raw: List[Tuple[float, int, float]], tol: float = 0.02
) -> List[Tuple[float, int, float]]:
    """
    和弦精简：将同一时刻（容差 tol 秒内）的多个音合并，仅保留音高最高的旋律音。
    raw 元素为 (start_sec, pitch, duration_sec)。
    """
    ordered = sorted(raw, key=lambda x: x[0])
    groups: List[Tuple[float, List[Tuple[float, int, float]]]] = []
    for item in ordered:
        if groups and abs(item[0] - groups[-1][0]) <= tol:
            groups[-1][1].append(item)
        else:
            groups.append((item[0], [item]))
    # 每组保留 pitch 最高的那个音
    return [max(items, key=lambda x: x[1]) for _, items in groups]


def parse_midi(
    path,
    simplify_chords: bool = True,
    min_duration_sec: float = 0.04,
) -> Score:
    """
    解析 MIDI 文件为曲谱。

    simplify_chords：和弦/同时多音只保留最高音（主旋律），降低杂音。
    min_duration_sec：时值小于该值（秒）的音符视为装饰音/碎音被过滤；0 表示不过滤。
    返回的曲谱中音符已按开始时间升序排序，时间单位为秒（根据 BPM 换算）。
    """
    path = Path(path)
    if not path.exists():
        raise MidiParseError(f"文件不存在：{path}")

    try:
        import music21
    except ImportError as exc:
        raise MidiParseError("未安装 music21，请先执行 pip install music21") from exc

    # 1. 解析
    try:
        score_obj = music21.converter.parse(str(path))
    except Exception as exc:
        raise MidiParseError(f"无法解析 MIDI 文件（格式可能不受支持）：{exc}") from exc

    # 2. 提取 BPM（默认 120）
    bpm: float = 120.0
    try:
        for mm in score_obj.flatten().getElementsByClass(music21.tempo.MetronomeMark):
            bpm = float(mm.number)
            break
    except Exception as exc:  # noqa: BLE001
        logger.warning("提取 BPM 失败，使用默认 120：%s", exc)

    if bpm <= 0:
        logger.warning("BPM 非法（%s），回退为 120", bpm)
        bpm = 120.0

    # 3. 收集原始音符（保留音高，供后续精简使用）
    raw: List[Tuple[float, int, float]] = []  # (start_sec, pitch, duration_sec)
    sec_per_quarter = 60.0 / bpm
    try:
        flat = score_obj.flatten()
        for el in flat.notesAndRests:
            # 跳过休止符等无音高元素
            if not (hasattr(el, "pitch") or hasattr(el, "pitches")):
                continue

            # offset 为四分音符单位（quarterLength），换算为秒
            start_sec = float(getattr(el, "offset", 0.0)) * sec_per_quarter
            try:
                quarter_len = float(el.duration.quarterLength)
            except Exception:  # noqa: BLE001
                quarter_len = 1.0
            duration_sec = quarter_len * sec_per_quarter

            if hasattr(el, "pitches"):  # 和弦：多个音
                pitches = [int(p.midi) for p in el.pitches]
            else:  # 单音
                pitches = [int(el.pitch.midi)]

            for midi_pitch in pitches:
                raw.append((start_sec, midi_pitch, duration_sec))
    except MidiParseError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise MidiParseError(f"提取音符失败：{exc}") from exc

    if not raw:
        raise MidiParseError("未从 MIDI 中提取到任何可演奏音符")

    # 4. 和弦精简：只留最高音
    if simplify_chords:
        before = len(raw)
        raw = _keep_highest_per_onset(raw)
        if len(raw) < before:
            logger.info("和弦精简：%d -> %d 个音符", before, len(raw))

    # 5. 过滤过短音符（装饰音/碎音）
    if min_duration_sec > 0:
        before = len(raw)
        filtered = [(s, p, d) for s, p, d in raw if d >= min_duration_sec]
        if filtered:  # 避免过滤后为空，仅在仍有音符时才采用
            if len(filtered) < before:
                logger.info("过滤过短音符：%d -> %d 个音符", before, len(filtered))
            raw = filtered

    # 6. 转换为键名并排序
    notes = [
        Note(key=pitch_to_key(p), start_sec=round(s, 4), duration_sec=round(d, 4))
        for s, p, d in raw
    ]
    notes.sort(key=lambda n: (n.start_sec, n.key))

    return Score(
        title=path.stem or "未命名曲谱",
        bpm=round(bpm, 2),
        notes=notes,
    )
