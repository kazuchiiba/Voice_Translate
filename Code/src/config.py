"""config.yaml と .env を読み込み、実行時設定を提供する。"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import yaml
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CODE_DIR = PROJECT_ROOT / "Code"
INPUT_DIR = PROJECT_ROOT / "Input"
OUTPUT_DIR = PROJECT_ROOT / "Output"
REFERENCE_DIR = PROJECT_ROOT / "Reference"
WORK_DIR = PROJECT_ROOT / "Work"

SUPPORTED_EXTENSIONS = {".m4a", ".wav", ".mp4"}


@dataclass(frozen=True)
class Settings:
    model: str
    language: str | None
    chunk_minutes: float
    max_parallel: int
    silence_thresh_db: float
    min_silence_len_sec: float
    speaker_change_pause_sec: float
    max_retries: int
    base_backoff_sec: float
    request_timeout_sec: float
    cleanup_work_files: bool
    openai_api_key: str


def load_settings(config_path: Path | None = None) -> Settings:
    config_path = config_path or (CODE_DIR / "config.yaml")

    load_dotenv(CODE_DIR / ".env")

    with open(config_path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY が環境変数に設定されていません。"
            f"Code/.env.example を Code/.env にコピーし、キーを設定してください（{CODE_DIR / '.env'}）。"
        )

    return Settings(
        model=raw["model"],
        language=raw.get("language"),
        chunk_minutes=float(raw["chunk_minutes"]),
        max_parallel=int(raw["max_parallel"]),
        silence_thresh_db=float(raw["silence_thresh_db"]),
        min_silence_len_sec=float(raw["min_silence_len_sec"]),
        speaker_change_pause_sec=float(raw["speaker_change_pause_sec"]),
        max_retries=int(raw["max_retries"]),
        base_backoff_sec=float(raw["base_backoff_sec"]),
        request_timeout_sec=float(raw["request_timeout_sec"]),
        cleanup_work_files=bool(raw["cleanup_work_files"]),
        openai_api_key=api_key,
    )
