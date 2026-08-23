# -*- coding: utf-8 -*-
"""曲谱数据模型与 JSON 导入/导出。"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import List, Tuple

from key_mapping import VALID_KEYS


@dataclass
class Note:
    """单个音符：对应键盘键、绝对开始时间（秒）、持续时长（秒）。"""
    key: str
    start_sec: float
    duration_sec: float


@dataclass
class Score:
    """曲谱：名称、BPM、音符列表。"""
    title: str
    bpm: float
    notes: List[Note] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "bpm": self.bpm,
            "notes": [
                {
                    "key": n.key,
                    "start_sec": round(n.start_sec, 4),
                    "duration_sec": round(n.duration_sec, 4),
                }
                for n in self.notes
            ],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    @classmethod
    def from_dict(cls, data: dict) -> "Score":
        if not isinstance(data, dict):
            raise ValueError("曲谱根节点必须是 JSON 对象")
        if "notes" not in data or not isinstance(data["notes"], list):
            raise ValueError("曲谱缺少 notes 数组")

        title = str(data.get("title", "未命名曲谱")).strip() or "未命名曲谱"
        try:
            bpm = float(data.get("bpm", 120))
        except (TypeError, ValueError):
            bpm = 120.0

        notes: List[Note] = []
        for i, item in enumerate(data["notes"]):
            if not isinstance(item, dict):
                raise ValueError(f"第 {i + 1} 个音符不是对象")
            for required in ("key", "start_sec", "duration_sec"):
                if required not in item:
                    raise ValueError(f"第 {i + 1} 个音符缺少字段 {required}")
            notes.append(Note(
                key=str(item["key"]).upper(),
                start_sec=float(item["start_sec"]),
                duration_sec=float(item["duration_sec"]),
            ))
        return cls(title=title, bpm=bpm, notes=notes)

    @classmethod
    def from_json(cls, text: str) -> "Score":
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError(f"JSON 解析失败：{exc}") from exc
        return cls.from_dict(data)


def validate_score(score: Score) -> Tuple[bool, List[str]]:
    """校验曲谱合法性，返回 (是否通过, 错误信息列表)。"""
    errors: List[str] = []
    for i, n in enumerate(score.notes):
        if n.key not in VALID_KEYS:
            errors.append(f"第 {i + 1} 个音符键名 '{n.key}' 非法（应为 QWERTY 三行中的字母）")
        if n.start_sec < 0:
            errors.append(f"第 {i + 1} 个音符 start_sec 为负数")
        if n.duration_sec <= 0:
            errors.append(f"第 {i + 1} 个音符 duration_sec 必须大于 0")
    if not (0 < score.bpm <= 1000):
        errors.append(f"bpm 值 {score.bpm} 不合理")
    return (len(errors) == 0), errors
