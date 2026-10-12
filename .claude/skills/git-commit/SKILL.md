---
name: git-commit
description: ユーザーが「コミットして」「commitして」「変更をgitに記録して」などと、gitへのコミットを明示的に依頼したときに使う。変更内容を調べてコミット対象ファイルとコミットメッセージ（タイトル）を提示し、ユーザーの確認を取ってからコミットする。pushは行わない（pushはgit-pushスキルを使う）。ユーザーが頼んでいないのに自主的にコミットする目的では使わない。
argument-hint: "[コミットしたい内容のメモ（任意）]"
---

# git-commit: 確認付きコミット

ユーザーの指示でコミットするための手順。コミットは **2段階確認の1段目** にあたる（2段目はgit-pushスキルのpush確認）。
`git commit` は `.claude/settings.json` で **ask** になっているので、実行時に必ず Claude Code の許可プロンプトが出る。そのプロンプトにはコミットメッセージを含むコマンド全体が表示されるので、これをユーザーの最終確認として使う。

引数（`$ARGUMENTS`）にメモがあれば、コミットメッセージや対象範囲を決める参考にする。

## 手順

### 1. 状態確認

```powershell
git rev-parse --show-toplevel
git status --short --branch
git diff --stat
git diff --cached --stat
git log --oneline -10
```

- gitリポジトリでない場合は、コミットせずに止める。ユーザーにリポジトリを作るか聞き、作る場合は **github-repo-create** スキルの手順に従う。
- 変更がなければ「コミットする変更はありません」と伝えて終了する。

### 2. コミット対象を決める

- ユーザーがファイルや範囲を指定していれば、それに従う。
- 指定がなければ、この会話で行った作業に関係する変更を対象にする。会話より前からあった無関係な変更（ユーザーの作業中の変更）は勝手に含めない。含めるか迷う場合はユーザーに聞く。
- `git add -A` や `git add .` は使わず、ファイルを明示して `git add <file> ...` する。

次のファイルは **コミットしない**。ステージされていたら除外し、`.gitignore` への追加を提案する。

- `.env` などの秘密情報（APIキー）。`.env.example` は値が空なのでコミットしてよい
- `Input/` の音声ファイル、`Output/` の文字起こし結果、`Reference/`（会議内容を含む個人・業務情報で、サイズも大きい）
- `Work/` などの一時ファイル、`.venv/`、`__pycache__/`
- `.claude/settings.local.json`（個人用設定）

### 3. 秘密情報チェック

ステージ後、差分にAPIキーなどが含まれていないか確認する。

```powershell
git diff --cached --name-only
git diff --cached | Select-String -Pattern 'sk-[A-Za-z0-9_-]{20,}|OPENAI_API_KEY\s*=\s*\S+|ghp_[A-Za-z0-9]{20,}|BEGIN (RSA |OPENSSH )?PRIVATE KEY'
```

見つかった場合はコミットせず、該当箇所をユーザーに報告する（キー自体は表示しない）。

### 4. コミットメッセージを作る

- `git log` に既存の履歴があれば、そのスタイル（言語・プレフィックスの有無・長さ）に合わせる。
- 履歴がなければ、一般的な **Conventional Commits** 形式にする。
  - タイトル: `<type>: <要約>`。type は `feat` / `fix` / `docs` / `refactor` / `test` / `chore` / `perf` / `build` / `ci` のいずれか。要約は日本語で50字程度まで。末尾に句点は付けない。
  - 本文（任意）: 「何を」より「なぜ」を書く。1コミット1目的にし、無関係な変更が混ざるならコミットを分けることを提案する。
- Claude Code から帰属表示（`Co-Authored-By:` 行）の指示があれば、本文の末尾に付ける。

### 5. 提示して確認を取る（1段階目）

コミットする前に、次の形でユーザーに提示する。

```
コミット内容の確認
- ブランチ: main
- 対象ファイル:
  - Code/src/transcribe.py（変更）
  - Code/config.yaml（変更）
- タイトル: fix: チャンク結合時の重複テキスト除去を修正
- 本文: オーバーラップ区間の…（あれば）

このあと git commit を実行します。許可プロンプトでタイトルを確認してください。
```

続けて `git add <files>` を実行し、次に `git commit` を実行する。タイトルと本文は `-m` で分けて渡す。

```powershell
git commit -m "fix: チャンク結合時の重複テキスト除去を修正" -m "本文"
```

- 許可プロンプトでユーザーが拒否した場合は、同じコマンドを再実行しない。何を直すか（タイトル、対象ファイルなど）を聞き、修正してから手順5をやり直す。
- `--amend`、`--no-verify`、`-a` は、ユーザーが明示的に頼んだ場合以外は使わない。
- pre-commit フックが失敗したら、原因を報告して修正する。フックを飛ばして通そうとしない。

### 6. 報告

```powershell
git log --oneline -1
git status --short --branch
```

コミットのハッシュとタイトルを報告する。pushはしない。ユーザーがpushも頼んでいれば、**git-push** スキルに進む。
