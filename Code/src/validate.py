"""DESIGN.md 3-2 ①：入力検証・メタ情報取得。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from . import ffmpeg_utils
from .config import SUPPORTED_EXTENSIONS

EXPECTED_MIN_SEC = 30 * 60
EXPECTED_MAX_SEC = 3 * 60 * 60


@dataclass(frozen=True)
class InputInfo:
    path: Path
    duration_sec: float
    warnings: list[str]


def validate_input(path: Path) -> InputInfo:
    warnings: list[str] = []

    if not path.exists():
        raise FileNotFoundError(f"入力ファイルが見つかりません: {path}")

    if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise ValueError(
            f"未対応の拡張子です: {path.suffix}（対応拡張子: {sorted(SUPPORTED_EXTENSIONS)}）"
        )

    duration_sec = ffmpeg_utils.get_duration_seconds(path)

    if duration_sec < EXPECTED_MIN_SEC or duration_sec > EXPECTED_MAX_SEC:
        warnings.append(
            f"音声の長さが想定範囲（30分〜3時間）外です: {duration_sec / 60:.1f}分"
            "（処理は継続しますが、処理時間が目標から外れる可能性があります）"
        )

    return InputInfo(path=path, duration_sec=duration_sec, warnings=warnings)
