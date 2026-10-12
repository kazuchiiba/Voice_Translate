# 音声文字起こしアプリ 論点・確認事項

実装に着手する前にユーザーに確認・決定してもらう必要がある項目をまとめる。
（DESIGN.md は確認済み・決定済みの設計のみを記載する方針のため、未決定の論点はここに分離している）

現時点で設計上の未確定の論点はなし（すべてDESIGN.mdに反映済み）。

## テスト実行時に発覚した問題

### [未解決] OpenAI APIのクレジット残高不足（TEST.md フェーズ2/3）

- **発生日**: 2026-10-12
- **内容**: `OPENAI_API_KEY` の認証自体は成功する（`client.models.list()` は200件取得できた）が、
  `audio.transcriptions.create` を3モデル（`gpt-4o-transcribe` / `gpt-4o-mini-transcribe` / `whisper-1`）
  すべてで実行したところ、全件が以下のエラーで失敗した。
  ```
  Error code: 429 - insufficient_quota / credit_balance_exhausted
  "You have no credits remaining. Add credits to continue using the API"
  ```
- **原因**: コードの問題ではなく、OpenAIアカウント側にクレジット（課金設定）が無い状態。
- **対応方法**: https://platform.openai.com/settings/organization/billing でクレジットを追加する必要がある。
- **影響**: TEST.md フェーズ3（モデル比較）・フェーズ4（E2E本番実行）が未実施。クレジット追加後に再実行する。
