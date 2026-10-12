---
name: github-repo-create
description: ユーザーが「GitHubにリポジトリを作って」「projectを立てて」「このフォルダをGitHubに登録して」などと依頼したとき、またはgit-pushスキルでpush先のremoteが未設定だったときに使う。GitHubアカウント名・リポジトリ名・公開範囲をユーザーに確認し、git init、.gitignoreの整備、gh repo create、originの設定までを行う。push自体はgit-pushスキルで行う。
argument-hint: "[owner/リポジトリ名（任意）]"
---

# github-repo-create: GitHubリポジトリ（project）の作成

`gh` CLI を使って、ローカルフォルダに対応する GitHub リポジトリを作る。
`gh repo create` は外部に公開される操作で、`.claude/settings.json` で **ask** になっている。リポジトリの削除（`gh repo delete`）は deny で禁止しているので、作成前に名前と公開範囲を確実に確認する。

引数（`$ARGUMENTS`）に `owner/name` があれば、それを候補として使う。

## 手順

### 1. gh の認証確認

```powershell
gh auth status
gh api user --jq .login
```

ログインしていない場合は、ユーザー自身に `! gh auth login` を実行してもらう。対話式のログインのため、Claude からは実行しない。

### 2. ユーザーに確認する

AskUserQuestion で次の点を聞く。推測で決めない。

| 項目 | 候補・既定値 |
|---|---|
| GitHubアカウント（owner） | `gh api user --jq .login` の結果。Organizationも指定できる |
| リポジトリ名 | フォルダ名（例: `20261010_Voice_Translate`） |
| 公開範囲 | **private（既定）** / public |
| 説明（任意） | 1行の説明 |
| リポジトリにするフォルダ | プロジェクトのルート（`.claude/` があるフォルダ） |

確認したら、同じ名前のリポジトリが既にないか調べる。

```powershell
gh repo view <owner>/<name> --json url,visibility
```

既にある場合は新しく作らない。「既存のリポジトリを origin に設定するか」をユーザーに聞く。

### 3. ローカルのgit初期化

```powershell
git rev-parse --show-toplevel   # 失敗すれば未初期化
git init -b main
```

既にgitリポジトリなら `git init` は実行しない。

### 4. .gitignore を整備する

最初のコミットより前に、次の項目が `.gitignore` にあることを確認する。足りない項目だけを追記し、既存の行は消さない。

```gitignore
# 秘密情報
.env
.claude/settings.local.json

# Python
.venv/
__pycache__/
*.pyc
.pytest_cache/

# 一時ファイル
Work/
tmp/
```

さらに、次の項目を除外するかをユーザーに確認する（既定は除外）。

- `Input/`（音声・動画）: サイズが大きく（GitHubは1ファイル100MBが上限）、会議の音声を含む
- `Output/`（文字起こし結果）と `Reference/`: 会議内容を含む個人・業務情報

`.claude/`（ガードレールとスキル）はチームで共有する設定なので、コミット対象にしてよい。

### 5. GitHubリポジトリを作成する

```powershell
gh repo create <owner>/<name> --private --source . --remote origin --description "<説明>"
```

- 公開範囲が public の場合は `--private` の代わりに `--public` を付ける。
- `--push` は付けない。最初のコミットとpushは、それぞれ git-commit スキルと git-push スキルで確認を取ってから行う。
- 許可プロンプトで拒否された場合は、再実行せずに何を変えるかを聞く。

### 6. 確認と報告

```powershell
git remote -v
gh repo view <owner>/<name> --json url,visibility --jq '.url + " (" + .visibility + ")"'
```

作成したリポジトリのURLと公開範囲を報告する。git-push スキルから呼ばれた場合は、git-push の手順（コミット → push）に戻る。
