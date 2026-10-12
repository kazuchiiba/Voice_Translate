"""imageio-ffmpeg が提供する ffmpeg 実行体のラッパー。システムffmpegは使わず、
プロジェクト内の仮想環境に閉じた実行体のみを使用する（DESIGN.md 5-2 ガードレール設定）。
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import imageio_ffmpeg

_DURATION_RE = re.compile(r"Duration:\s*(\d+):(\d{2}):(\d{2}(?:\.\d+)?)")
_SILENCE_START_RE = re.compile(r"silence_start:\s*([\d.]+)")
_SILENCE_END_RE = re.compile(r"silence_end:\s*([\d.]+)")


def ffmpeg_exe() -> str:
    return imageio_ffmpeg.get_ffmpeg_exe()


def run_ffmpeg(args: list[str]) -> str:
    """ffmpeg を実行し、stderr（ffmpegは通常ログをstderrに出す）を文字列で返す。"""
    cmd = [ffmpeg_exe(), "-hide_banner", *args]
    proc = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return proc.stderr


def get_duration_seconds(input_path: Path) -> float:
    """ffmpeg -i の stderr から Duration を読み取る（ffprobe不要）。"""
    stderr = run_ffmpeg(["-i", str(input_path)])
    match = _DURATION_RE.search(stderr)
    if not match:
        raise RuntimeError(f"音声の長さを取得できませんでした: {input_path}\n{stderr}")
    hours, minutes, seconds = match.groups()
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def extract_mono_wav(input_path: Path, output_path: Path, sample_rate: int = 16000) -> None:
    """解析用（無音検出用）のモノラル16kHz WAVを生成する。元ファイルは変更しない。"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    stderr = run_ffmpeg(
        [
            "-y",
            "-i", str(input_path),
            "-ac", "1",
            "-ar", str(sample_rate),
            "-vn",
            str(output_path),
        ]
    )
    if not output_path.exists():
        raise RuntimeError(f"音声の前処理に失敗しました: {input_path}\n{stderr}")


def detect_silences(wav_path: Path, thresh_db: float, min_silence_len_sec: float) -> list[tuple[float, float]]:
    """ffmpeg の silencedetect フィルタで無音区間 [(start_sec, end_sec), ...] を検出する。"""
    stderr = run_ffmpeg(
        [
            "-i", str(wav_path),
            "-af", f"silencedetect=noise={thresh_db}dB:d={min_silence_len_sec}",
            "-f", "null",
            "-",
        ]
    )
    starts = [float(m.group(1)) for m in _SILENCE_START_RE.finditer(stderr)]
    ends = [float(m.group(1)) for m in _SILENCE_END_RE.finditer(stderr)]
    return list(zip(starts, ends))


def extract_chunk_wav(
    input_path: Path,
    output_path: Path,
    start_sec: float,
    end_sec: float,
    sample_rate: int = 16000,
) -> None:
    """元ファイルから [start_sec, end_sec) を再エンコードして切り出す（劣化を抑えるため
    ストリームコピーではなく明示的な再エンコードを用いる）。"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    duration = end_sec - start_sec
    stderr = run_ffmpeg(
        [
            "-y",
            "-ss", f"{start_sec:.3f}",
            "-i", str(input_path),
            "-t", f"{duration:.3f}",
            "-ac", "1",
            "-ar", str(sample_rate),
            "-vn",
            str(output_path),
        ]
    )
    if not output_path.exists():
        raise RuntimeError(f"チャンクの切り出しに失敗しました: {input_path} [{start_sec}, {end_sec})\n{stderr}")
