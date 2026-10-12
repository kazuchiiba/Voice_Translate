"""DESIGN.md 3-2 ③：無音区間検出によるチャンク分割。

オーバーラップは使わない。無音区間の中点で切ることで単語を分断せず、
かつ重複テキストの機械的除去（あいまいな文字列マッチング）を不要にする。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from . import ffmpeg_utils


@dataclass(frozen=True)
class ChunkSpan:
    index: int
    start_sec: float
    end_sec: float


def compute_chunk_boundaries(
    total_duration_sec: float,
    silences: list[tuple[float, float]],
    chunk_target_sec: float,
) -> list[ChunkSpan]:
    """無音区間リストを使い、chunk_target_sec を超えたら直後の無音区間の中点で切る。
    無音が見つからない場合は chunk_target_sec の位置で強制的に切る。
    """
    silence_midpoints = sorted((s + e) / 2 for s, e in silences)
    search_window_sec = chunk_target_sec / 2

    boundaries: list[float] = []
    cursor = 0.0
    while cursor + chunk_target_sec < total_duration_sec:
        target = cursor + chunk_target_sec
        window_lo, window_hi = target - search_window_sec, target + search_window_sec
        candidates = [m for m in silence_midpoints if cursor < m <= window_hi and m >= window_lo]
        # 無音が見つからない場合はtarget位置で強制的に切る（発話中を分断するが、全体を止めないための最終手段）
        cut_point = min(candidates, key=lambda m: abs(m - target)) if candidates else target
        boundaries.append(cut_point)
        cursor = cut_point

    spans: list[ChunkSpan] = []
    start = 0.0
    for i, b in enumerate(boundaries):
        spans.append(ChunkSpan(index=i, start_sec=start, end_sec=b))
        start = b
    spans.append(ChunkSpan(index=len(spans), start_sec=start, end_sec=total_duration_sec))
    return spans


def split_into_chunks(
    input_path: Path,
    work_dir: Path,
    chunk_minutes: float,
    silence_thresh_db: float,
    min_silence_len_sec: float,
) -> list[tuple[ChunkSpan, Path]]:
    """入力ファイルを解析してチャンク境界を決定し、各チャンクをWork配下に書き出す。
    戻り値は (ChunkSpan, 切り出したWAVファイルパス) のリスト。
    """
    analysis_wav = work_dir / "_analysis.wav"
    ffmpeg_utils.extract_mono_wav(input_path, analysis_wav)

    total_duration = ffmpeg_utils.get_duration_seconds(input_path)
    silences = ffmpeg_utils.detect_silences(analysis_wav, silence_thresh_db, min_silence_len_sec)
    spans = compute_chunk_boundaries(total_duration, silences, chunk_minutes * 60)

    results: list[tuple[ChunkSpan, Path]] = []
    for span in spans:
        chunk_path = work_dir / f"chunk_{span.index:03d}.wav"
        ffmpeg_utils.extract_chunk_wav(input_path, chunk_path, span.start_sec, span.end_sec)
        results.append((span, chunk_path))

    return results
