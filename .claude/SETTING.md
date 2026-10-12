# Claude Code 設定（ガードレールとスキル）

このプロジェクトに設定した Claude Code のガードレールとスキルをまとめたものです。設定日は 2026-10-12 です。

## 1. 前提

- **有効になる条件**
  - `settings.json` とフック（ガードレール）は、**このフォルダ（`20261010_Voice_Translate`）を Claude Code のプロジェクトルートとして開いたとき**だけ有効になります。
  - 親の `test_code` を開いた場合は、親側の `.claude/` の設定が使われます。
  - スキルは、どちらを開いた場合でも読み込まれます。
- **ガードレールの限界**
  - ガードレールはベストエフォートのソフトな仕組みで、OS レベルのサンドボックスではありません。通常の誤操作や事故は防げますが、巧妙な迂回まですべて防げるわけではありません。
  - フック（PowerShell スクリプト）が起動できなかった場合は「ブロックしない」側に倒れます。ただし `settings.json` の deny / ask ルールは引き続き効きます。
- **全体の方針**
  - 基本はネット上で一般的に推奨されている設定に従っています。
  - 一般的な設定より厳しくしたのは「ファイル削除」だけです。
  - git の操作は、禁止ではなく「毎回確認（ask）」にしています。

## 2. ファイル構成

```text
20261010_Voice_Translate/
├── SETTING.md                     # このファイル
└── .claude/
    ├── README.md                  # 概要（簡易版）
    ├── settings.json              # 許可ルール（allow / ask / deny）とフックの登録
    ├── guardrail.json             # フックの設定（作業範囲・削除してよい一時領域）
    ├── hooks/
    │   ├── guard-workdir.ps1      # プロジェクト外へのアクセスを禁止
    │   └── guard-destructive.ps1  # 削除・秘密情報・ダウンロード即実行を検査
    └── skills/
        ├── git-commit/SKILL.md
        ├── git-push/SKILL.md
        └── github-repo-create/SKILL.md
```

## 3. ガードレール

### 3-1. 全体像

| 対象 | 扱い | 実装場所 |
|---|---|---|
| 一時領域のファイル削除 | 確認なしで許可 | `guard-destructive.ps1` |
| 一時領域以外のファイル削除 | **禁止** | `guard-destructive.ps1` |
| 削除先を検証できない削除 | **禁止** | `guard-destructive.ps1` |
| git の履歴・リモート操作 | **毎回確認（ask）** | `settings.json` |
| GitHub リポジトリ作成、PR、リリース | **毎回確認（ask）** | `settings.json` |
| `git clean`、`gh repo delete` | **禁止** | `settings.json` と `guard-destructive.ps1` |
| 秘密情報（`.env`、SSH 鍵、AWS 認証情報） | **読み取り禁止** | `settings.json` と `guard-destructive.ps1` |
| `Input/`、`Reference/` の編集 | **禁止** | `settings.json` |
| ダウンロードしたスクリプトをそのまま実行（`curl ... \| bash` など） | **禁止** | `guard-destructive.ps1` |
| `sudo`、`Format-Volume` | **禁止** | `settings.json` |
| パッケージのインストール・削除（`pip install` など） | **毎回確認（ask）** | `settings.json` |
| プロジェクト外のファイルの読み書き | **禁止** | `guard-workdir.ps1` |
| ガードレール自身の設定ファイルの編集 | **毎回確認（ask）** | `settings.json` |
| bypass モード（`--dangerously-skip-permissions`） | **使用不可** | `settings.json` の `disableBypassPermissionsMode` |

ルールの優先順位は **deny（禁止） > ask（確認） > allow（許可）** です。フックが deny を返した場合も禁止になります。

### 3-2. ファイル削除（`guard-destructive.ps1`）

一般的な設定では `rm -rf` だけを禁止することが多いですが、このプロジェクトでは「AIが勝手にファイルを消さない」ことを優先し、**一時領域以外の削除はすべて禁止**しています。

**削除してよい場所**（`guardrail.json` で変更できます）

| 種類 | 対象 |
|---|---|
| `deletableTempDirs` | `Work/`、`tmp/`、`temp/`、`.tmp/`（プロジェクト直下） |
| `deletableCacheDirNames` | `__pycache__`、`.pytest_cache`、`.mypy_cache`、`.ruff_cache`（階層は問わない） |
| OS の一時フォルダ | `%TEMP%`、`$env:TEMP`、Git Bash の `/tmp`（一時フォルダ自体の削除は不可） |

`Work/` は DESIGN.md で「一時ファイル。処理完了後に削除可」とされているため、一時領域に含めています。

**判定の仕方**

1. 次の削除コマンドを検出します: `rm` / `rmdir` / `rd` / `del` / `erase` / `ri` / `unlink` / `shred` / `rimraf` / `Remove-Item` / `Clear-Content`。`sh -c "..."` の中に書かれている場合も検出します。
2. 削除対象のパスを取り出して絶対パスに直し、`..` も解決したうえで、上の一時領域の中かどうかを確かめます。
3. 判定結果は次のとおりです。
   - コマンド全体が一時領域の削除だけ → **確認なしで許可**
   - 一時領域の削除に別のコマンドが混ざっている → 通常どおり**許可プロンプトが出る**（別のコマンドが確認なしで通るのを防ぐため）
   - 一時領域以外のパスが含まれる → **禁止**
   - 削除対象を特定できない → **禁止**。次のような場合が該当します。
     - 変数を使っている（`Remove-Item $x`）
     - パイプで渡している（`Get-ChildItem | Remove-Item`）
     - フォルダ名にワイルドカードが付いている（`Work*` は `WorkImportant` にも一致するため）

**削除先を検証できないため、常に禁止しているもの**

- Python: `os.remove` / `os.unlink` / `os.rmdir` / `shutil.rmtree` / `Path.unlink` / `send2trash`
- .NET: `[IO.File]::Delete`、`[IO.Directory]::Delete`、`.Delete()`
- `robocopy /MIR`、`robocopy /PURGE`（コピー先のファイルを消すため）
- `find -delete`、`find -exec rm`
- `git clean`（git でも復元できない未追跡ファイルを消すため）
- `Format-Volume`、`Clear-Disk`、`Clear-RecycleBin`
- `gh repo delete`、`gh api -X DELETE`

これはコマンドラインからの実行だけが対象です。アプリ本体（`main.py` など）が設定 `cleanup_work_files` に従って `Work/` を片付ける処理は、この制限を受けません。

**誤検知の対策**

`git commit -m "..."` や `gh repo create --description "..."` など、文章を引数に取るコマンドでは、引用符の中の文字（「rm」「del」「.env」など）を無視します。引用符の外にあるコマンド（例: `git commit -m "x"; rm -rf Code`）は検査します。

### 3-3. git / GitHub（`settings.json`）

**確認なしで許可（読み取り系・取り消しやすいもの）**

`git status` / `git diff` / `git log` / `git show` / `git fetch` / `git add` / `git branch --show-current` / `git remote -v` / `git remote get-url` / `gh auth status` / `gh repo view`

**毎回確認（ask）**

| 分類 | コマンド |
|---|---|
| 履歴を作る・送る | `git commit` / `git push` / `git pull` / `git merge` / `git tag` / `git cherry-pick` / `git revert` |
| 変更を捨てる・履歴を書き換える | `git reset` / `git restore` / `git checkout` / `git switch` / `git stash` / `git rebase` / `git filter-branch` |
| ファイル操作 | `git rm` / `git mv` |
| ブランチ・リモート・設定 | `git branch -<オプション>` / `git remote add / set-url / remove / rename` / `git config` |
| GitHub | `gh repo create` / `gh repo edit` / `gh pr` / `gh release` |

force push（`git push --force`）や `git reset --hard` も、禁止ではなく ask で止まります。許可プロンプトにはコマンド全体が表示されるので、内容を見てから承認してください。

### 3-4. 秘密情報

| ルール | 意味 |
|---|---|
| `Read(.env)`、`Read(.env.*)`、`Read(!.env.example)` | `.env` 系のファイルは読み取り禁止（階層は問わない）。ただし値の入っていない `.env.example` は読める |
| `Edit(.env)` | `.env` の編集を禁止 |
| `Read(~/.ssh/**)`、`Read(~/.aws/**)` | SSH 鍵と AWS 認証情報の読み取りを禁止 |
| フックによる検査 | `Get-Content .env`、`cat .env` など、シェルから `.env`・`secrets.toml`・`id_rsa` などにアクセスするコマンドを禁止 |

### 3-5. プロジェクト外へのアクセス（`guard-workdir.ps1`）

`guardrail.json` の `allowedProjectDirs`（`"."` は、このフォルダのみを意味します）の外にあるファイルについて、次を禁止します。

- Read / Edit / Write / Glob / Grep での読み書き・検索
- シェルコマンドでの `..` や、プロジェクト外の絶対パスの指定

`test_code` の兄弟プロジェクトにある `guard-workdir.ps1` と同じ仕組みです。

### 3-6. ブロックされた操作を実行したいとき

Claude にガードレールを外させるのではなく、ご自身で `!` を付けて実行してください。

```text
! Remove-Item Output\old_result.txt
```

ガードレールの設定ファイル（`settings.json`、`guardrail.json`、`hooks/`）を Claude が編集しようとした場合も、許可プロンプトが出ます。

## 4. スキル

チャットで指示すると、Claude が該当するスキルを自動で使います。`/git-commit` のようにスラッシュコマンドとして呼び出すこともできます。
どのスキルも、**ユーザーが明示的に頼んだときだけ**使う前提で、Claude が自主的にコミットや push をすることはありません。

### 4-1. 全体の流れ（2段階確認）

```text
「pushして」
   │
   ├─ remote が未設定？ ──Yes──▶ [github-repo-create]
   │                              アカウント名・リポジトリ名・公開範囲を質問
   │                              → .gitignore 整備 → gh repo create（ask）
   │
   ├─ 未コミットの変更がある？ ──Yes──▶ [git-commit]
   │                                    対象ファイルとタイトルを提示
   │                                    → git commit（ask）  ← 1段階目の確認
   │
   └─ [git-push]
        リモートとの差分を確認 → 送信するコミットを提示
        → git push（ask）  ← 2段階目の確認
```

### 4-2. git-commit

| 項目 | 内容 |
|---|---|
| 使い方の例 | 「コミットして」「commitして」「変更をgitに記録して」 |
| 役割 | 2段階確認の **1段階目**。push はしない |

**手順**

1. `git status`、`git diff`、`git log` で状態を確認します。git リポジトリでなければ、github-repo-create に案内します。
2. コミット対象を決めます。
   - 今回の作業に関係するファイルだけを、ファイル名を指定して `git add` します（`git add -A` は使いません）。
   - 会話より前からあった無関係な変更は、勝手に含めません。
3. 次のファイルはコミットしません。
   - `.env`
   - `Input/`、`Output/`、`Reference/`
   - `Work/`、`.venv/`、`__pycache__/`
   - `settings.local.json`
4. ステージした差分に API キー（`sk-...`、`OPENAI_API_KEY=値`、`ghp_...`、秘密鍵）が含まれていないか確認します。
5. コミットメッセージを作ります。
   - 既存の履歴があれば、そのスタイルに合わせます。
   - 履歴がなければ Conventional Commits 形式（`feat: ...`、`fix: ...` など。日本語で50字程度）にします。
6. ブランチ・対象ファイル・タイトル・本文を提示し、`git commit` を実行します。許可プロンプトにタイトルが表示されるので、そこで確認してください。
7. プロンプトで拒否した場合、同じコマンドは再実行されません。Claude が修正点を聞きます。

`--amend`、`--no-verify`、`-a` は、明示的に頼んだときしか使いません。

### 4-3. git-push

| 項目 | 内容 |
|---|---|
| 使い方の例 | 「pushして」「GitHubに上げて」「リモートに反映して」 |
| 役割 | 2段階確認の **2段階目** |

**手順**

1. ブランチ、remote、状態を確認します。
2. **push 先が決まっていない場合**（git 未初期化、または remote 未設定）は、次の3点を質問します。
   - GitHub アカウント（候補はログイン中のアカウント）
   - リポジトリ名（候補はフォルダ名）
   - 公開範囲（既定は private）

   回答を受けたら、github-repo-create でリポジトリを作り、git-commit でコミットしてから push に進みます。
3. 未コミットの変更があれば、先にコミットするかを聞きます。コミットしない場合、stash や restore で変更に触れることはしません。
4. `git fetch` でリモートとの差分を確認します。リモートの方が進んでいる場合は push せずに報告します。force push はしません。
5. remote・ブランチ・送信するコミットの一覧を提示し、`git push`（初回は `git push -u origin <branch>`）を実行します。許可プロンプトで確認してください。
6. push したブランチ、コミット数、リポジトリの URL を報告します。

### 4-4. github-repo-create

| 項目 | 内容 |
|---|---|
| 使い方の例 | 「GitHubにprojectを立てて」「リポジトリを作って」。git-push から自動で呼ばれる場合もあります |
| 役割 | GitHub リポジトリを作り、origin に設定する（push はしない） |

**手順**

1. `gh auth status` で認証を確認します。ログインしていない場合は、ご自身で `! gh auth login` を実行してください。
2. アカウント（owner）、リポジトリ名、公開範囲（既定は private）、説明を質問します。推測では決めません。
3. 同じ名前のリポジトリが既にある場合は新しく作らず、既存のリポジトリを origin に設定するかを聞きます。
4. 未初期化なら `git init -b main` を実行します。
5. 最初のコミットより前に `.gitignore` を整えます。
   - 常に除外: `.env`、`settings.local.json`、`.venv/`、`__pycache__/`、`Work/`、`tmp/` など
   - 除外するか確認する（既定は除外）: `Input/`（音声・大容量。GitHub の上限は1ファイル100MB）、`Output/`、`Reference/`（会議内容を含む）
   - `.claude/`（ガードレールとスキル）はコミット対象にします。
6. `gh repo create <owner>/<name> --private --source . --remote origin` を実行します。許可プロンプトが出ます。`--push` は付けません。
7. 作成したリポジトリの URL と公開範囲を報告します。

## 5. 設定の変更方法

| やりたいこと | 編集するファイル |
|---|---|
| 削除してよい一時フォルダを増やす・減らす | `.claude/guardrail.json` の `deletableTempDirs` / `deletableCacheDirNames` |
| 確認なしで実行してよいコマンドを増やす | `.claude/settings.json` の `allow` |
| git 操作などを確認なしにする・禁止にする | `.claude/settings.json` の `ask` から `allow` / `deny` へ移す |
| 自分だけの設定を足す（共有しない） | `.claude/settings.local.json`（新規作成。git にはコミットしない） |
| スキルの手順を変える | `.claude/skills/<スキル名>/SKILL.md` |

## 6. 検証状況

| 対象 | 状況 |
|---|---|
| `guard-destructive.ps1` | 29 ケースを直接実行し、すべて期待どおりの結果だった（2026-10-12） |
| `settings.json` | JSON として正しく読めることを確認済み |
| `settings.json` の ask / deny ルール、スキル | 実際のセッションでの動作は未確認 |

ask / deny ルールとスキルは、このフォルダを Claude Code のルートとして開き、「コミットして」と指示して確認してください。

`guard-destructive.ps1` のテストケースの内訳:

- **許可されること**: `Work\` 配下・`%TEMP%`・`__pycache__`・`/tmp` の削除
- **禁止されること**:
  - `Code\`・`Input\`・`Output\` の削除、`rm -rf .`、`Work*`、`Work/../Code`
  - パイプや変数を使った削除、`sh -c "rm ..."`
  - `os.remove`、`.NET Delete`、`robocopy /MIR`、`git clean`
  - `.env` の読み取り、`curl | bash`
- **誤検知しないこと**: `.env.example` の読み取り、commit メッセージ中の「rm」、`git rm --cached`、通常の python 実行

## 7. 参考にした情報

- [Configure permissions – Claude Code Docs](https://code.claude.com/docs/en/permissions)
- [Hooks – Claude Code Docs](https://code.claude.com/docs/en/hooks)
- [Skills – Claude Code Docs](https://code.claude.com/docs/en/skills)
- [cc-safe-setup SETTINGS_REFERENCE](https://cdn.jsdelivr.net/npm/cc-safe-setup@29.8.0/SETTINGS_REFERENCE.md)
- [fast.io: Claude Code permissions setup guide](https://fast.io/resources/claude-code-permissions-setup-guide/)
- [How to build your own Claude Code skill (freeCodeCamp)](https://www.freecodecamp.org/news/how-to-build-your-own-claude-code-skill)
