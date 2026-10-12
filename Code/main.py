"""CLIエントリポイント（DESIGN.md 6章 実装手順9）。

使い方:
    python main.py                  # Input/ 内の全対応ファイルを処理
    python main.py ファイル名.m4a    # Input/ 内の指定ファイルのみ処理
"""

from __future__ import annotations

import sys
from pathlib import Path

from src.config import INPUT_DIR, SUPPORTED_EXTENSIONS, load_settings
from src.pipeline import process_file


def resolve_targets(args: list[str]) -> list[Path]:
    if not args:
        return sorted(
            p for p in INPUT_DIR.iterdir()
            if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS
        )
    targets = []
    for arg in args:
        p = Path(arg)
        if not p.is_absolute():
            p = INPUT_DIR / arg
        targets.append(p)
    return targets


def main() -> None:
    settings = load_settings()
    targets = resolve_targets(sys.argv[1:])

    if not targets:
        print(f"処理対象ファイルが見つかりません: {INPUT_DIR}")
        return

    for path in targets:
        try:
            process_file(path, settings)
        except Exception as e:  # noqa: BLE001
            print(f"[{path.name}] エラー: {e}")


if __name__ == "__main__":
    main()
