"""DESIGN.md 3-2 ④：並列文字起こし。

temperature=0 の確定的出力のみを使用し、プロンプトによる文脈補正は行わない
（「推論させない」原則。DESIGN.md 3章）。

話者変更に伴う改行（DESIGN.md 3章）は、whisper-1のセグメントタイムスタンプ自体には
頼らない（実際の無音とは無関係に機械的に区切られており、ギャップが常に0のため使えないことが
実機検証で判明：ISSUE.md参照）。代わりに、チャンク音声に対して独自にffmpegの無音検出
（ffmpeg_utils.detect_silences）を行い、検出した無音区間の直後に来るセグメントの境界で
改行を挿入する。無音の「検出」は音声信号の機械的な処理であり、テキスト内容の解釈・推論は行わない。
"""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path

from openai import OpenAI

from . import ffmpeg_utils
from .chunking import ChunkSpan


@dataclass
class ChunkResult:
    span: ChunkSpan
    text: str | None  # 失敗時は None
    error: str | None = None
    retries_used: int = 0


def probe_verbose_json_support(
    client: OpenAI,
    model: str,
    language: str | None,
    sample_chunk_path: Path,
    timeout_sec: float,
) -> bool:
    """最初のチャンクで一度だけ verbose_json (segment timestamps) 対応を確認する。"""
    try:
        with open(sample_chunk_path, "rb") as f:
            kwargs = dict(model=model, file=f, temperature=0, response_format="verbose_json")
            if language:
                kwargs["language"] = language
            response = client.with_options(timeout=timeout_sec).audio.transcriptions.create(**kwargs)
        return bool(getattr(response, "segments", None))
    except Exception:
        return False


def _find_break_segment_indices(segments, silences: list[tuple[float, float]]) -> set[int]:
    """検出した無音区間ごとに、その終了直後に始まる最初のセグメントのインデックスを「改行位置」とする。"""
    break_indices: set[int] = set()
    for _silence_start, silence_end in silences:
        for i, seg in enumerate(segments):
            start = seg.start if hasattr(seg, "start") else seg["start"]
            if start >= silence_end:
                break_indices.add(i)
                break
    return break_indices


def _segments_to_text(segments, break_indices: set[int]) -> str:
    """セグメント文字列をそのまま連結する。改行位置として特定されたセグメントの直前にのみ
    改行を挿入する。テキスト内容そのものには一切手を加えない。"""
    parts: list[str] = []
    for i, seg in enumerate(segments):
        text = seg.text if hasattr(seg, "text") else seg["text"]
        if i in break_indices and i != 0:
            parts.append("\n")
        parts.append(text)
    return "".join(parts).strip()


def _transcribe_one(
    client: OpenAI,
    model: str,
    language: str | None,
    chunk_path: Path,
    timeout_sec: float,
    use_verbose_json: bool,
    silence_thresh_db: float,
    min_silence_sec: float,
) -> str:
    with open(chunk_path, "rb") as f:
        kwargs = dict(
            model=model,
            file=f,
            temperature=0,
            response_format="verbose_json" if use_verbose_json else "text",
        )
        if language:
            kwargs["language"] = language
        response = client.with_options(timeout=timeout_sec).audio.transcriptions.create(**kwargs)

    if use_verbose_json:
        segments = getattr(response, "segments", None)
        if segments:
            silences = ffmpeg_utils.detect_silences(chunk_path, silence_thresh_db, min_silence_sec)
            break_indices = _find_break_segment_indices(segments, silences)
            return _segments_to_text(segments, break_indices)
        return getattr(response, "text", str(response))
    return response if isinstance(response, str) else getattr(response, "text", str(response))


def transcribe_chunk_with_retry(
    client: OpenAI,
    model: str,
    language: str | None,
    span: ChunkSpan,
    chunk_path: Path,
    max_retries: int,
    base_backoff_sec: float,
    timeout_sec: float,
    use_verbose_json: bool,
    silence_thresh_db: float,
    min_silence_sec: float,
) -> ChunkResult:
    last_error: str | None = None
    for attempt in range(max_retries + 1):
        try:
            text = _transcribe_one(
                client, model, language, chunk_path, timeout_sec,
                use_verbose_json, silence_thresh_db, min_silence_sec,
            )
            return ChunkResult(span=span, text=text, retries_used=attempt)
        except Exception as e:  # noqa: BLE001 - APIエラー種別を問わずリトライ対象とする
            last_error = str(e)
            if attempt < max_retries:
                time.sleep(base_backoff_sec * (2 ** attempt))
    return ChunkResult(span=span, text=None, error=last_error, retries_used=max_retries)


def transcribe_chunks(
    api_key: str,
    model: str,
    language: str | None,
    chunks: list[tuple[ChunkSpan, Path]],
    max_parallel: int,
    max_retries: int,
    base_backoff_sec: float,
    timeout_sec: float,
    silence_thresh_db: float,
    min_silence_sec: float,
) -> list[ChunkResult]:
    client = OpenAI(api_key=api_key)

    use_verbose_json = False
    if chunks:
        first_span, first_path = chunks[0]
        use_verbose_json = probe_verbose_json_support(client, model, language, first_path, timeout_sec)

    results: dict[int, ChunkResult] = {}
    with ThreadPoolExecutor(max_workers=max_parallel) as executor:
        futures = {
            executor.submit(
                transcribe_chunk_with_retry,
                client, model, language, span, chunk_path,
                max_retries, base_backoff_sec, timeout_sec,
                use_verbose_json, silence_thresh_db, min_silence_sec,
            ): span.index
            for span, chunk_path in chunks
        }
        for future in as_completed(futures):
            result = future.result()
            results[result.span.index] = result

    return [results[i] for i in sorted(results)]
