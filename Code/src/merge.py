"""DESIGN.md 3-2 ⑤：チャンク結合・タイムスタンプ正規化。

オーバーラップを使わない設計（chunking.py参照）のため、重複除去は不要。
各チャンクの開始・終了時刻（自前のチャンク分割で判明済み）をそのままタイムスタンプとして使う。
"""

from __future__ import annotations

from .transcribe import ChunkResult


def format_timestamp(seconds: float) -> str:
    total_seconds = int(seconds)
    h, rem = divmod(total_seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def merge_results(results: list[ChunkResult]) -> str:
    blocks: list[str] = []
    for r in results:
        ts_start = format_timestamp(r.span.start_sec)
        ts_end = format_timestamp(r.span.end_sec)
        header = f"[{ts_start} - {ts_end}]"
        if r.text is not None:
            blocks.append(f"{header}\n{r.text}")
        else:
            blocks.append(f"{header}\n[文字起こし失敗: {r.error}]")
    return "\n\n".join(blocks) + "\n"
