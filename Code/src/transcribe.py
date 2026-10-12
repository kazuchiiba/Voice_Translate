"""DESIGN.md 3-2 ④：並列文字起こし。

temperature=0 の確定的出力のみを使用し、プロンプトによる文脈補正は行わない
（「推論させない」原則。DESIGN.md 3章）。

話者変更に伴う改行（DESIGN.md 3章）は、ASRが返すセグメント単位のタイムスタンプ
（verbose_json）のギャップでのみ判定する。モデルがverbose_jsonに対応していない
場合は、この機能を無効化し、プレーンテキストのまま出力する（テキスト内容自体の
推論・言い換えは一切行わない）。
"""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path

from openai import OpenAI

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


def _segments_to_text(segments, pause_threshold_sec: float) -> str:
    """セグメント間のギャップ（無音ポーズ）が閾値以上なら改行2つを挿入する。
    テキスト内容そのものには一切手を加えない。"""
    parts: list[str] = []
    prev_end: float | None = None
    for seg in segments:
        text = seg.text if hasattr(seg, "text") else seg["text"]
        start = seg.start if hasattr(seg, "start") else seg["start"]
        end = seg.end if hasattr(seg, "end") else seg["end"]
        if prev_end is not None and (start - prev_end) >= pause_threshold_sec:
            parts.append("\n")
        parts.append(text)
        prev_end = end
    return "".join(parts).strip()


def _transcribe_one(
    client: OpenAI,
    model: str,
    language: str | None,
    chunk_path: Path,
    timeout_sec: float,
    use_verbose_json: bool,
    pause_threshold_sec: float,
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
            return _segments_to_text(segments, pause_threshold_sec)
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
    pause_threshold_sec: float,
) -> ChunkResult:
    last_error: str | None = None
    for attempt in range(max_retries + 1):
        try:
            text = _transcribe_one(
                client, model, language, chunk_path, timeout_sec,
                use_verbose_json, pause_threshold_sec,
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
    pause_threshold_sec: float,
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
                use_verbose_json, pause_threshold_sec,
            ): span.index
            for span, chunk_path in chunks
        }
        for future in as_completed(futures):
            result = future.result()
            results[result.span.index] = result

    return [results[i] for i in sorted(results)]
