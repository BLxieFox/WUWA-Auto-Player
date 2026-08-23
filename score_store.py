# -*- coding: utf-8 -*-
"""曲谱库存储：以本地 JSON 文件形式管理曲谱。"""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import List

from score_model import Score, validate_score

logger = logging.getLogger("WuwaAutoPlayer")


def _sanitize_filename(title: str) -> str:
    """将曲谱标题转换为合法的文件名。"""
    cleaned = re.sub(r'[\\/:*?"<>|\r\n\t]+', "_", title).strip()
    cleaned = re.sub(r"\s+", "_", cleaned).strip("_.")
    return cleaned or "untitled"


class ScoreStore:
    """负责曲谱的持久化保存与读取。"""

    def __init__(self, base_dir: Path):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _path_for(self, title: str) -> Path:
        return self.base_dir / f"{_sanitize_filename(title)}.json"

    def save(self, score: Score) -> Path:
        """保存曲谱（按标题命名，同名会覆盖）。返回保存路径。"""
        path = self._path_for(score.title)
        path.write_text(score.to_json(), encoding="utf-8")
        logger.info("曲谱已保存：%s", path)
        return path

    def list_titles(self) -> List[str]:
        """列出曲谱库中所有曲谱标题。"""
        titles: List[str] = []
        for p in sorted(self.base_dir.glob("*.json")):
            try:
                score = Score.from_json(p.read_text(encoding="utf-8"))
                titles.append(score.title)
            except Exception as exc:  # noqa: BLE001
                logger.warning("跳过无法读取的曲谱文件 %s：%s", p.name, exc)
                titles.append(p.stem)
        return titles

    def load(self, title: str) -> Score:
        """按标题加载曲谱。"""
        path = self._path_for(title)
        if not path.exists():
            # 兜底：尝试按文件名前缀模糊匹配
            matched = list(self.base_dir.glob(f"{_sanitize_filename(title)}*.json"))
            if not matched:
                raise FileNotFoundError(f"曲谱文件不存在：{path}")
            path = matched[0]

        text = path.read_text(encoding="utf-8")
        score = Score.from_json(text)
        ok, errors = validate_score(score)
        if not ok:
            logger.warning("曲谱 [%s] 校验发现问题：%s", score.title, "; ".join(errors))
        return score

    def delete(self, title: str) -> bool:
        """按标题删除曲谱。"""
        path = self._path_for(title)
        if path.exists():
            path.unlink()
            return True
        return False
