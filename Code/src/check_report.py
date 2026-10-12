"""DESIGN.md 3-2 ⑦：Reference比較・チェックレポート生成。

Referenceはあくまで成果物確認用。本文（Output/{name}.txt）には一切書き戻さない。
"""

from __future__ import annotations

import difflib
import re
from pathlib import Path

_TIMESTAMP_HEADER_RE = re.compile(r"^\[[\d:]+ - [\d:]+\]$")


def _strip_timestamps(transcript_text: str) -> str:
    lines = [line for line in transcript_text.splitlines() if not _TIMESTAMP_HEADER_RE.match(line.strip())]
    return "\n".join(line for line in lines if line.strip() != "")


def generate_check_report(reference_text: str, transcript_text: str) -> str:
    body_only = _strip_timestamps(transcript_text)

    ref_lines = reference_text.splitlines()
    gen_lines = body_only.splitlines()

    matcher = difflib.SequenceMatcher(a=ref_lines, b=gen_lines, autojunk=False)
    ratio = matcher.ratio()

    diff_lines = list(
        difflib.unified_diff(ref_lines, gen_lines, fromfile="Reference", tofile="Output", lineterm="")
    )

    report = [
        "# チェックレポート（Reference比較・確認用）",
        "",
        "このレポートは Output の文字起こし本文を自動修正するものではありません。",
        "差分は人間が確認するための参考情報です。",
        "",
        f"- 一致率（SequenceMatcher ratio）: {ratio:.3f}",
        "",
        "## 差分（unified diff: Reference → Output）",
        "",
        "```diff",
        *diff_lines,
        "```",
    ]
    return "\n".join(report) + "\n"


def write_check_report_if_reference_exists(
    reference_dir: Path, output_dir: Path, name: str, transcript_text: str
) -> Path | None:
    reference_path = reference_dir / f"{name}.txt"
    if not reference_path.exists():
        return None

    reference_text = reference_path.read_text(encoding="utf-8")
    report = generate_check_report(reference_text, transcript_text)

    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / f"{name}.check_report.md"
    report_path.write_text(report, encoding="utf-8")
    return report_path
