"""DESIGN.md 3-2 全体処理フローのオーケストレーション。"""

from __future__ import annotations

import shutil
import time
from pathlib import Path

from . import check_report, output, validate
from .chunking import split_into_chunks
from .config import OUTPUT_DIR, REFERENCE_DIR, WORK_DIR, Settings
from .merge import merge_results
from .transcribe import transcribe_chunks


def process_file(input_path: Path, settings: Settings) -> None:
    name = input_path.stem
    work_dir = WORK_DIR / name

    print(f"[{name}] 入力検証中...")
    info = validate.validate_input(input_path)
    for w in info.warnings:
        print(f"[{name}] 警告: {w}")
    print(f"[{name}] 音声長: {info.duration_sec / 60:.1f}分")

    t0 = time.time()

    print(f"[{name}] チャンク分割中...")
    chunks = split_into_chunks(
        input_path=input_path,
        work_dir=work_dir,
        chunk_minutes=settings.chunk_minutes,
        silence_thresh_db=settings.silence_thresh_db,
        min_silence_len_sec=settings.min_silence_len_sec,
    )
    print(f"[{name}] チャンク数: {len(chunks)}")

    print(f"[{name}] 文字起こし中（並列数: {settings.max_parallel}）...")
    results = transcribe_chunks(
        api_key=settings.openai_api_key,
        model=settings.model,
        language=settings.language,
        chunks=chunks,
        max_parallel=settings.max_parallel,
        max_retries=settings.max_retries,
        base_backoff_sec=settings.base_backoff_sec,
        timeout_sec=settings.request_timeout_sec,
        pause_threshold_sec=settings.speaker_change_pause_sec,
    )

    failed = [r for r in results if r.text is None]
    if failed:
        print(f"[{name}] 警告: {len(failed)}件のチャンクが失敗しました（プレースホルダーを出力します）")

    transcript_text = merge_results(results)

    txt_path = output.write_transcript(OUTPUT_DIR, name, transcript_text)
    json_path = output.write_segments_json(OUTPUT_DIR, name, results)
    print(f"[{name}] 出力: {txt_path}")
    print(f"[{name}] 出力: {json_path}")

    report_path = check_report.write_check_report_if_reference_exists(
        REFERENCE_DIR, OUTPUT_DIR, name, transcript_text
    )
    if report_path:
        print(f"[{name}] チェックレポート: {report_path}")

    if settings.cleanup_work_files and work_dir.exists():
        shutil.rmtree(work_dir, ignore_errors=True)

    elapsed_min = (time.time() - t0) / 60
    print(f"[{name}] 完了（処理時間: {elapsed_min:.1f}分）")
