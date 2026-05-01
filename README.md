# 📚 rss-paper-digest

RSSフィードから論文を自動取得し、[Claude API](https://www.anthropic.com/) で自分の研究関心との関連度スコアリングと日本語要約を行い、Markdownダイジェストを生成するツールです。

**`config.yaml` を書き換えるだけで、どんな研究分野・ジャーナルにも対応できます。**

## 特徴

- **YAML設定**: コードを編集せずに、フィードURL・研究関心をカスタマイズ可能
- **スコアリング**: Claude API が研究関心との関連度を1〜5で自動評価
- **日本語要約**: score 3以上の論文はアブストラクトを100字以内で要約
- **重複スキップ**: 過去に処理した論文は `seen_urls.json` で管理し再処理しない
- **GitHub Actions**: 設定した曜日・時刻に自動実行し、Markdownをリポジトリに保存

## セットアップ

### 1. リポジトリをコピーする

右上の **Use this template → Create a new repository** を選択してください。
自分のアカウントに独立したリポジトリが作成されます。

### 2. 設定ファイルを編集

`config.yaml` を自分の研究関心・フィードに合わせて編集してください（後述）。

### 3. Anthropic API キーを取得

[Anthropic Console](https://console.anthropic.com/) で API キーを発行してください。
APIを利用するには最低5ドルのクレジットが必要ですが、5ドルでもかなり使えるので、まずは少額チャージして試してみることをおすすめします。

## 設定ファイル（config.yaml）

`config.yaml` を直接編集して使います。

```yaml
# フィードあたりの最大取得件数
max_papers_per_feed: 10

# 使用する Claude モデル
model: "claude-sonnet-4-6"

# RSSフィードURL一覧
feeds:
  - "https://rss.sciencedirect.com/publication/science/00472727"
  - "https://www.nature.com/nature.rss"
  # URLを追加・削除するだけでカスタマイズできます

# 研究関心（スコアリングの基準）
research_interests: |
  - 因果推論（DiD、RDD、IV）
  - 労働経済学・賃金・雇用
  - 日本の公共政策
  # 自分の関心に合わせて自由に書き換えてください
```

## 実行方法

### 方法1: ローカルで実行する

> **手元の環境ですぐ試せる方法です。** 設定の確認や動作テストに向いています。

#### 前提条件

- [uv](https://docs.astral.sh/uv/) がインストールされていること（[インストール方法](https://docs.astral.sh/uv/getting-started/installation/)）
- Python 3.12 以上

#### 手順

```bash
# 1. リポジトリをクローン
git clone https://github.com/<あなたのユーザー名>/rss-paper-digest.git
cd rss-paper-digest

# 2. 依存パッケージをインストール
uv sync

# 3. APIキーを設定
cp .env.example .env
# .env を編集: ANTHROPIC_API_KEY=sk-ant-xxxxxxxx

# 4. 実行
uv run python main.py
```

#### dry-run（APIを呼ばずにRSSフェッチのみ確認）

```bash
uv run python main.py --dry-run
```

取得した論文タイトルとURLを一覧表示します。`seen_urls.json` の更新・Markdownの生成は行いません。API呼び出し前の動作確認に便利です。

#### 実行ログ例

```
2026-04-28 08:00:01 [INFO] 設定ファイル: config.yaml
2026-04-28 08:00:01 [INFO] フィード数: 5 件 / フィードあたり上限: 10 件
2026-04-28 08:00:01 [INFO] 既処理URL数: 0
2026-04-28 08:00:01 [INFO] RSSフィードを取得中...
2026-04-28 08:00:05 [INFO]   [Journal of Public Economics] 10 件の新規論文を取得
...
2026-04-28 08:00:08 [INFO] 新規論文数: 47 件
2026-04-28 08:00:08 [INFO] Claude API (claude-sonnet-4-6) でスコアリング中...
2026-04-28 08:00:15 [INFO] スコア分布: score 5: 3件  score 4: 8件  score 3: 11件  ...
2026-04-28 08:00:15 [INFO] 使用トークン: input=14200, output=3500, cache_creation=9800, cache_read=4400
2026-04-28 08:00:15 [INFO] ダイジェスト生成完了: output/2026-04-28.md
```

---

### 方法2: GitHub Actions で自動実行する

> **一度設定すれば、あとは自動で定期実行されます。** ローカル環境のセットアップは不要で、生成された Markdown がリポジトリに自動的に蓄積されます。

#### 前提条件

- テンプレートから自分のアカウントにリポジトリを作成済みであること

#### 手順

**1. Anthropic API キーを GitHub Secrets に登録する**

1. 作成したリポジトリの **Settings → Secrets and variables → Actions**
2. **New repository secret** をクリック
3. 名前: `ANTHROPIC_API_KEY`、値: `sk-ant-xxxxxxxx` を登録

**2. スケジュールを設定する**

`.github/workflows/digest.yml` の `cron` を好みのスケジュールに変更してコミットしてください。

```yaml
# 例: 毎日 07:00 JST (= 22:00 UTC)
- cron: "0 22 * * *"

# 例: 月曜・水曜・金曜 08:00 JST
- cron: "0 23 * * 0,2,4"
```

`cron` の時間は UTC で指定する必要があるため、日本時間から9時間引いた値を設定してください。曜日を指定する場合は、0=日曜, 1=月曜, ..., 6=土曜 となります。書き方は [GitHub Actions のドキュメント](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule) を参照してください。

設定後はスケジュールに従って自動実行され、生成された `output/YYYY-MM-DD.md` と `seen_urls.json` がリポジトリに自動コミット・プッシュされます。

**手動で今すぐ実行したい場合**は、Actions タブから **Run workflow** を選択してください。

## 出力フォーマット（output/YYYY-MM-DD.md）

```markdown
# 📚 Paper Digest — 2026-04-28

## ⭐⭐⭐⭐⭐ 必読（score: 5）
**[Journal of Public Economics] Fiscal Transfers and Regional Growth**
📝 財政移転が地域成長に与える因果効果をDiDで推定。日本の地方交付税データを使用。
💡 DiD×地方財政の直接的関連
🔗 https://...

## ⭐⭐⭐⭐ 読む価値あり（score: 4）
...

## ⭐⭐⭐ 参考程度（score: 3）
...

## ⭐⭐ スキップ推奨（score: 1-2）
- [Research Policy] Patent thickets and innovation...（特許のみで政策評価なし）
```

## ディレクトリ構成

```
rss-paper-digest/
├── pyproject.toml          # uv プロジェクト設定
├── uv.lock                 # 依存バージョンロックファイル
├── .env                    # ANTHROPIC_API_KEY（要作成、git管理外）
├── .env.example            # .env のテンプレート
├── .gitignore
├── config.example.yaml     # 設定ファイルのテンプレート
├── config.yaml             # ユーザー設定（研究関心・フィードURL）
├── config_loader.py        # YAML設定の読み込み
├── main.py                 # エントリポイント
├── fetcher.py              # RSSフェッチ・既読URL管理
├── scorer.py               # Claude APIスコアリング・要約
├── reporter.py             # Markdownダイジェスト生成
├── seen_urls.json          # 処理済みURL記録（自動生成）
├── output/                 # 生成ダイジェスト保存先
│   └── YYYY-MM-DD.md
└── .github/workflows/
    └── digest.yml          # GitHub Actions
```

## ライセンス

[MIT License](LICENSE)
