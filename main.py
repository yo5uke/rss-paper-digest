"""
main.py: エントリポイント

使い方:
  uv run python main.py              # 通常実行
  uv run python main.py --dry-run    # APIを呼ばずにRSSフェッチのみ確認
  uv run python main.py --config path/to/config.yaml  # 設定ファイルを指定
"""

import argparse
import logging
import sys
from collections import Counter
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from config_loader import load_config
from fetcher import fetch_papers, load_seen_urls, save_seen_urls
from reporter import generate_report
from scorer import score_papers


def _setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stdout,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="RSS Paper Digest Generator")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="RSSフェッチのみ実行し、API呼び出しとファイル生成をスキップする",
    )
    parser.add_argument(
        "--config",
        default="config.yaml",
        metavar="FILE",
        help="設定ファイルのパス（デフォルト: config.yaml）",
    )
    args = parser.parse_args()

    _setup_logging()
    logger = logging.getLogger(__name__)

    # ── 1. 設定を読み込む ──────────────────────────────────────────────────
    try:
        config = load_config(Path(args.config))
    except (FileNotFoundError, ValueError) as e:
        logger.error(str(e))
        sys.exit(1)

    logger.info(f"設定ファイル: {args.config}")
    logger.info(f"フィード数: {len(config.feeds)} 件 / フィードあたり上限: {config.max_papers_per_feed} 件")

    # ── 2. 既処理URLを読み込む ──────────────────────────────────────────────
    seen_urls = load_seen_urls()
    logger.info(f"既処理URL数: {len(seen_urls)}")

    # ── 3. 新規論文を取得 ──────────────────────────────────────────────────
    logger.info("RSSフィードを取得中...")
    papers = fetch_papers(config.feeds, seen_urls, config.max_papers_per_feed)
    logger.info(f"新規論文数: {len(papers)} 件")

    if not papers:
        logger.info("新規論文がありません。終了します。")
        return

    # ── 4. dry-run モード ──────────────────────────────────────────────────
    if args.dry_run:
        logger.info("【dry-run】取得論文一覧:")
        for i, p in enumerate(papers, 1):
            print(f"  [{i:3}] [{p['journal']}] {p['title']}")
            print(f"        URL: {p['url']}")
        logger.info("--dry-run: API呼び出しをスキップしました。")
        return

    # ── 5. Claude API でスコアリング ────────────────────────────────────────
    logger.info(f"Claude API ({config.model}) でスコアリング中...")
    try:
        scored_papers, usage = score_papers(
            papers, config.research_interests, config.model
        )
    except EnvironmentError as e:
        logger.error(str(e))
        sys.exit(1)
    except Exception as e:
        logger.error(f"スコアリング中に予期しないエラーが発生しました: {e}")
        sys.exit(1)

    dist = Counter(p["score"] for p in scored_papers)
    dist_str = "  ".join(
        f"score {s}: {c}件" for s, c in sorted(dist.items(), reverse=True)
    )
    logger.info(f"スコア分布: {dist_str}")
    logger.info(
        f"使用トークン: "
        f"input={usage['input_tokens']}, "
        f"output={usage['output_tokens']}, "
        f"cache_creation={usage['cache_creation_input_tokens']}, "
        f"cache_read={usage['cache_read_input_tokens']}"
    )

    # ── 6. Markdown ダイジェストを生成 ─────────────────────────────────────
    today = date.today().isoformat()
    output_path = Path("output") / f"{today}.md"
    generate_report(scored_papers, today, output_path)
    logger.info(f"ダイジェスト生成完了: {output_path}")

    # ── 7. 処理済みURLを保存 ───────────────────────────────────────────────
    new_urls = {p["url"] for p in papers}
    save_seen_urls(seen_urls | new_urls)
    logger.info(f"seen_urls.json を更新しました（累計: {len(seen_urls) + len(new_urls)} 件）")


if __name__ == "__main__":
    main()
