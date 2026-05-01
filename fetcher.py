"""
fetcher.py: RSSフィードの取得と既読URL管理を担当します。
"""

import json
import logging
import re
from pathlib import Path

import feedparser

logger = logging.getLogger(__name__)

SEEN_URLS_FILE = Path("seen_urls.json")


def load_seen_urls() -> set[str]:
    """seen_urls.json から既処理URLセットを読み込む。ファイルがなければ空setを返す。"""
    if not SEEN_URLS_FILE.exists():
        return set()
    try:
        with open(SEEN_URLS_FILE, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return set(data)
        logger.warning("seen_urls.json の形式が不正です。空のセットとして扱います。")
        return set()
    except (json.JSONDecodeError, OSError) as e:
        logger.warning(f"seen_urls.json の読み込みに失敗しました: {e}")
        return set()


def save_seen_urls(seen_urls: set[str]) -> None:
    """処理済みURLセットを seen_urls.json に保存する。"""
    try:
        with open(SEEN_URLS_FILE, "w", encoding="utf-8") as f:
            json.dump(sorted(seen_urls), f, ensure_ascii=False, indent=2)
    except OSError as e:
        logger.error(f"seen_urls.json の保存に失敗しました: {e}")


def _clean_text(text: str, max_len: int = 1000) -> str:
    """HTMLタグを除去し、空白を正規化して最大文字数に切り詰める。"""
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > max_len:
        text = text[:max_len] + "..."
    return text


def fetch_papers(
    feeds: list[str],
    seen_urls: set[str],
    max_papers_per_feed: int = 10,
) -> list[dict]:
    """
    フィードリストから新規論文を取得する。

    Parameters
    ----------
    feeds               : RSSフィードURLのリスト
    seen_urls           : 既処理URLのセット（重複スキップに使用）
    max_papers_per_feed : フィードあたりの最大取得件数

    Returns
    -------
    新規論文の辞書リスト。各辞書は title / journal / abstract / url を持つ。
    """
    papers: list[dict] = []

    for feed_url in feeds:
        try:
            feed = feedparser.parse(feed_url)

            if feed.bozo and feed.bozo_exception:
                logger.warning(
                    f"フィード解析警告 ({feed_url}): {feed.bozo_exception}"
                )

            journal_name: str = feed.feed.get("title", feed_url)
            entries = feed.entries[:max_papers_per_feed]
            new_count = 0

            for entry in entries:
                url: str = entry.get("link", "").strip()
                if not url or url in seen_urls:
                    continue

                title = _clean_text(entry.get("title", "（タイトルなし）"), max_len=300)
                abstract = _clean_text(
                    entry.get("summary", entry.get("description", "")),
                    max_len=1000,
                )

                papers.append(
                    {
                        "title": title,
                        "journal": journal_name,
                        "abstract": abstract,
                        "url": url,
                    }
                )
                new_count += 1

            logger.info(f"  [{journal_name}] {new_count} 件の新規論文を取得")

        except Exception as e:
            logger.error(f"フィード取得エラー ({feed_url}): {e}")
            continue

    return papers
