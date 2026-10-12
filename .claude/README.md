# .claude（ガードレールとスキル）

このフォルダ（`20261010_Voice_Translate`）を **Claude Code のプロジェクトルートとして開いたとき** に有効になる設定です。
`settings.json` とフックは、ルートとして開いたフォルダの `.claude/` からのみ読み込まれます。`test_code` を開いた場合は親側の設定が使われます。スキルはどちらで開いても読み込まれます。

## ガードレール

| 対象 | 扱い | 仕組み |
|---|---|---|
| ファイル削除（`rm` / `del` / `Remove-Item` など） | 一時領域だけ許可（確認なし）。それ以外は禁止 | `hooks/guard-destructive.ps1` |
| 対象を検証できない削除（`python os.remove`、`shutil.rmtree`、`.NET Delete`、`robocopy /MIR`、`find -delete`、`git clean`、変数やパイプ経由の削除） | 常に禁止 | 同上 |
| git の履歴・リモート操作（commit / push / pull / reset / rebase / checkout / restore / stash / rm / tag / remote変更 など） | 毎回確認（ask） | `settings.json` |
| `gh repo create` / `gh pr` / `pip install` | 毎回確認（ask） | `settings.json` |
| `.env`・SSH鍵などの秘密情報の読み取り | 禁止 | `settings.json` とフック |
| `Input/`・`Reference/` の編集 | 禁止 | `settings.json` |
| `curl ... \| bash` などのダウンロード即実行、`sudo` | 禁止 | フックと `settings.json` |
| プロジェクト外のファイルの読み書き | 禁止 | `hooks/guard-workdir.ps1` |
| ガードレール自身の設定ファイルの編集 | 毎回確認（ask） | `settings.json` |
| `--dangerously-skip-permissions`（bypassモード） | 使用不可 | `disableBypassPermissionsMode` |

削除してよい一時領域は `guardrail.json` で変更できます。

- `deletableTempDirs`: `Work/`、`tmp/`、`temp/`、`.tmp/`
- `deletableCacheDirNames`: `__pycache__` などのキャッシュフォルダ（階層は問いません）
- OSの一時フォルダ（`%TEMP%`）は常に削除できます。

ブロックされた操作を本当に実行したい場合は、プロンプトで `!` を付けてご自身で実行してください（例: `! Remove-Item Output\old.txt`）。

> これらはベストエフォートのソフトガードレールで、OSレベルのサンドボックスではありません。通常の誤操作は防げますが、巧妙な迂回をすべて防げるわけではありません。

## スキル

| スキル | 使い方の例 | 内容 |
|---|---|---|
| `git-commit` | 「コミットして」 | 対象ファイルとタイトルを提示し、許可プロンプトで確認してからコミットします（1段階目） |
| `git-push` | 「pushして」 | 送信するコミットを提示し、許可プロンプトで確認してからpushします（2段階目）。remoteが未設定なら、アカウント名とリポジトリ名を聞いてリポジトリを作ってからコミット・pushします |
| `github-repo-create` | 「GitHubにprojectを立てて」 | `gh` で private リポジトリを作成し、`.gitignore` を整備して origin に設定します |
