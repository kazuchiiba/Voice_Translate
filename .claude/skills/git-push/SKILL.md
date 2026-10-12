---
name: git-push
description: ユーザーが「pushして」「GitHubに上げて」「リモートに反映して」などと、gitのpushを明示的に依頼したときに使う。push先のリモートを確認し、送信するコミットの一覧を提示してから、ユーザーの許可を取ってpushする。remote（GitHubリポジトリ）が未設定なら、GitHubアカウント名とリポジトリ名を聞いてリポジトリを作成し、未コミットの変更をコミットしてからpushする。ユーザーが頼んでいないのに自主的にpushする目的では使わない。
argument-hint: "[ブランチ名（任意）]"
---

# git-push: 確認付きpush

ユーザーの指示でpushするための手順。pushは **2段階確認の2段目** にあたる（1段目はgit-commitスキルのコミット確認）。
`git push` は `.claude/settings.json` で **ask** になっているので、実行時に必ず許可プロンプトが出る。pushは取り消しが難しい操作なので、実行前に送信内容を必ず提示する。

## 手順

### 1. 状態確認

```powershell
git rev-parse --show-toplevel
git branch --show-current
git remote -v
git status --short --branch
```

### 2. push先が決まっていない場合（初回push）

次のどれかに当てはまる場合は、push先のプロジェクトが決まっていない。

- gitリポジトリではない
- `origin` などのremoteが設定されていない

この場合は、推測でリポジトリを作らない。AskUserQuestion で次の点をユーザーに聞く。

1. **GitHubアカウント（owner）**: `gh api user --jq .login` で取得したログイン中のアカウントを候補として示す。Organizationを指定してもよい。
2. **リポジトリ名**: フォルダ名（例: `20261010_Voice_Translate`）を候補として示す。
3. **公開範囲**: 既定は `private`。`public` にする場合は、音声や文字起こしなどの個人・業務情報を含まないことを確認する。

回答を受けたら、**github-repo-create** スキルの手順でリポジトリを作り、`origin` に設定する。
そのあと、未コミットの変更があれば **git-commit** スキルの手順でコミットし（1段階目の確認）、手順3以降でpushする（2段階目の確認）。

### 3. 未コミットの変更がある場合

`git status` に変更が残っていれば、「未コミットの変更があります。先にコミットしますか？」とユーザーに聞く。

- コミットする場合は、**git-commit** スキルに従う。
- コミットしない場合は、コミット済みの分だけpushする。未コミットの変更には触れない（stash や restore はしない）。

### 4. リモートとの差分確認

```powershell
git fetch origin
git status --short --branch
git log --oneline origin/<branch>..HEAD
```

- リモートにまだブランチがない場合（初回push）は、`git log --oneline -20` を送信内容として使う。
- リモートが先に進んでいる（behind / diverged）場合は、pushしない。状況を報告し、`git pull`（ask）で取り込むかをユーザーに聞く。
- `--force` / `--force-with-lease` / `+refspec` は、ユーザーが理由を含めて明示的に頼んだ場合以外は使わない。

### 5. 提示してpushする（2段階目）

push前に、次の形でユーザーに提示する。

```
push内容の確認
- リモート: origin (https://github.com/<owner>/<repo>.git)
- ブランチ: main → origin/main
- 送信するコミット（2件）:
  - a1b2c3d fix: チャンク結合時の重複テキスト除去を修正
  - d4e5f6a docs: DESIGN.md に出力形式を追記

このあと git push を実行します。許可プロンプトで承認してください。
```

続けて push する。

```powershell
git push                          # upstream 設定済みの場合
git push -u origin <branch>       # 初回（upstream 未設定）の場合
```

許可プロンプトでユーザーが拒否した場合は、再実行せずに理由を聞く。

### 6. 報告

```powershell
git status --short --branch
gh repo view --json url --jq .url
```

pushしたブランチ、コミット数、リポジトリのURLを報告する。
