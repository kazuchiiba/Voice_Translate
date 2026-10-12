# Voice_Translate

会議・説明などの音声ファイル（30分〜3時間程度）を入力し、OpenAI API（`whisper-1`）で精緻に文字起こしするツール。

後で音声を聞き直しながら照合する用途を前提としているため、**ASRの生出力に忠実**であること（要約・言い換え・推論的な補完をしないこと）を最優先に設計している。詳細な設計方針は [`Code/DESIGN.md`](Code/DESIGN.md) を参照。

## 特徴

- 音声を無音区間でチャンク分割し、OpenAI APIへ並列リクエストすることで、3時間の音声でも数分〜数十分で処理が完了する
- 文字起こし結果を**言い換えない**：要約・フィラー語削除・文法修正などは一切行わない
- 出力は3形式
  - `*.txt` … タイムスタンプ付き逐語本文
  - `*_Ver0.1.docx` … 議事メモ用Wordファイル（`Sample/` のテンプレート書式を再現。箇条書き・ページ番号付き）
  - `*.segments.json` … チャンク単位の生データ（デバッグ・やり直し用）
- `Reference/` に同名のテキストファイルを置くと、文字起こし結果との差分チェックレポート（`*.check_report.md`）を自動生成（本文は書き換えない、あくまで人間の確認用）
- チャンク単位のリトライ・失敗時プレースホルダー出力で、一部区間が失敗しても全体処理は継続する

## 必要環境

- Python 3.12系
- OpenAI APIキー（`whisper-1` が利用できるアカウント、クレジット残高が必要）
- システムへのffmpegインストールは不要（`imageio-ffmpeg` が仮想環境内にffmpeg実行体を同梱する）

## セットアップ

```bash
cd Code
python -m venv .venv

# Windows
.venv\Scripts\python.exe -m pip install -r requirements.txt

# APIキーを設定
copy .env.example .env
# .env を開き、OPENAI_API_KEY=sk-... を実際のキーに書き換える
```

## 使い方

1. `Input/` フォルダに音声ファイル（`.m4a` / `.wav` / `.mp4`）を置く
2. （任意）`Reference/` に同名の `.txt` を置くと、後で差分チェックレポートが生成される
3. 実行

```bash
cd Code
.venv\Scripts\python.exe main.py                   # Input/ 内の全対応ファイルを処理
.venv\Scripts\python.exe main.py ファイル名.m4a      # 指定ファイルのみ処理
```

4. `Output/` フォルダに `{ファイル名}.txt` / `{ファイル名}_Ver0.1.docx` / `{ファイル名}.segments.json` が生成される

## 設定（`Code/config.yaml`）

| 項目                             | 内容                                                           |
| -------------------------------- | -------------------------------------------------------------- |
| `model`                          | 使用するASRモデル（`whisper-1`。比較検証の経緯はDESIGN.md参照）|
| `language`                       | 文字起こし対象言語（`ja`固定。自動判定にする場合は`null`）     |
| `chunk_minutes`                  | 1チャンクの目標長（分）                                         |
| `max_parallel`                   | API同時リクエスト数                                             |
| `silence_thresh_db` / `min_silence_len_sec` | チャンク分割用の無音検出パラメータ                   |
| `speaker_change_min_silence_sec` | 箇条書き項目を改行する無音ポーズの最短長（秒）                   |
| `max_retries` / `base_backoff_sec` | チャンク失敗時のリトライ回数・待機時間                         |
| `cleanup_work_files`             | 処理完了後に`Work/`内の中間ファイルを削除するか                 |

## フォルダ構成

```
20261010_Voice_Translate/
├── Code/              # 実装コード（本README、DESIGN.md、ISSUE.md、TEST.md含む）
├── Input/             # 入力音声ファイル
├── Reference/         # （任意）チェック用の既存テキスト
├── Output/            # 文字起こし結果の出力先
├── Sample/            # Word出力の書式テンプレート参考元
└── Work/              # 一時ファイル（処理完了後に自動削除）
```

## ドキュメント

- [`Code/DESIGN.md`](Code/DESIGN.md) … 設計方針・処理フローの詳細
- [`Code/ISSUE.md`](Code/ISSUE.md) … 検証過程で見つかった既知の問題・保留事項
- [`Code/TEST.md`](Code/TEST.md) … 動作テスト計画

## 既知の制限

- whisper-1は稀に同一フレーズを繰り返すハルシネーションを起こすことがある（低頻度）。本文は自動修正されないため、聞き直しでの確認を推奨
- whisper-1のセグメントタイムスタンプは実際の無音と連動しないため、改行（箇条書き項目の区切り）は独自の無音検出で補っているが、完全ではない

詳細は [`Code/ISSUE.md`](Code/ISSUE.md) を参照。
