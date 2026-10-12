"""DESIGN.md 3-2 ⑥：出力生成。"""

from __future__ import annotations

import json
from pathlib import Path

from .merge import format_timestamp
from .transcribe import ChunkResult


def write_transcript(output_dir: Path, name: str, transcript_text: str) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{name}.txt"
    path.write_text(transcript_text, encoding="utf-8")
    return path


def write_segments_json(output_dir: Path, name: str, results: list[ChunkResult]) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{name}.segments.json"
    data = [
        {
            "index": r.span.index,
            "start_sec": r.span.start_sec,
            "end_sec": r.span.end_sec,
            "start_ts": format_timestamp(r.span.start_sec),
            "end_ts": format_timestamp(r.span.end_sec),
            "status": "ok" if r.text is not None else "failed",
            "retries_used": r.retries_used,
            "error": r.error,
            "text": r.text,
        }
        for r in results
    ]
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return path
