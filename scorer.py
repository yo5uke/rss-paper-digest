"""
scorer.py: Claude API を使って論文のスコアリングと日本語要約を行います。

- Prompt Caching を活用してシステムプロンプト（研究関心）をキャッシュし、
  複数バッチ呼び出し時のコストを削減します。
- API / JSON パースエラー時はログに記録してデフォルト値（score=1）を返し、
  スクリプト全体を止めません。
"""

import json
import logging
import os

import anthropic

logger = logging.getLogger(__name__)

BATCH_SIZE = 20  # 1回のAPI呼び出しあたりの最大論文数


def _build_system_prompt(research_interests: str) -> str:
    return f"""あなたは研究者アシスタントです。
以下の研究関心に基づいて、論文の関連度をスコアリングし、要約を行ってください。

## 研究関心
{research_interests}

## 採点基準
- score 5: 研究関心と非常に高い関連性（必読）
- score 4: 研究関心と高い関連性（読む価値あり）
- score 3: 研究関心とある程度の関連性（参考程度）
- score 2: 研究関心との関連性が低い
- score 1: 研究関心との関連性がほぼない

## 出力形式
以下のJSON配列**のみ**を出力してください（前後の説明文・コードブロック不要）：
[
  {{
    "index": 1,
    "score": 5,
    "reason": "関連/非関連の理由（30字以内の日本語）",
    "summary": "日本語要約（100字以内）"
  }}
]

注意：
- score が 3 未満の場合、summary は空文字列 "" にする
- reason は必ず30字以内の日本語
- summary は必ず100字以内の日本語（score >= 3 の場合のみ）
- 入力された論文すべてに対してエントリを返すこと"""


def _build_papers_text(papers: list[dict]) -> str:
    parts = []
    for i, paper in enumerate(papers, 1):
        abstract = paper.get("abstract") or "（アブストラクトなし）"
        parts.append(
            f"[{i}]\n"
            f"タイトル: {paper['title']}\n"
            f"ジャーナル: {paper['journal']}\n"
            f"アブストラクト: {abstract}\n"
            f"URL: {paper['url']}"
        )
    return "\n\n".join(parts)


def _default_scored(papers: list[dict], reason: str = "スコア取得失敗") -> list[dict]:
    return [{**p, "score": 1, "reason": reason, "summary": ""} for p in papers]


def _parse_response_text(raw: str) -> list[dict]:
    """APIレスポンスからJSONを抽出してパースする。"""
    text = raw.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        inner = []
        in_block = False
        for line in lines:
            if line.startswith("```") and not in_block:
                in_block = True
                continue
            if line.startswith("```") and in_block:
                break
            if in_block:
                inner.append(line)
        text = "\n".join(inner).strip()
    return json.loads(text)


def _score_batch(
    papers: list[dict],
    client: anthropic.Anthropic,
    system_content: str,
    model: str,
) -> tuple[list[dict], dict | None]:
    """1バッチ分の論文をスコアリングする。エラー時はデフォルト値を返す。"""
    papers_text = _build_papers_text(papers)
    try:
        response = client.messages.create(
            model=model,
            max_tokens=8192,
            system=[
                {
                    "type": "text",
                    "text": system_content,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"以下の {len(papers)} 件の論文をスコアリングしてください。\n\n"
                        f"{papers_text}"
                    ),
                }
            ],
        )
    except anthropic.APIError as e:
        logger.error(f"Claude API エラー: {e}")
        return _default_scored(papers, "API エラー"), None

    raw_text = response.content[0].text
    try:
        items = _parse_response_text(raw_text)
    except (json.JSONDecodeError, IndexError, ValueError) as e:
        logger.error(f"JSON パースエラー: {e}")
        logger.debug(f"レスポンス先頭500字: {raw_text[:500]}")
        return _default_scored(papers, "JSON パースエラー"), None

    score_map = {item["index"]: item for item in items if isinstance(item, dict)}
    scored: list[dict] = []
    for i, paper in enumerate(papers, 1):
        sp = paper.copy()
        if i in score_map:
            item = score_map[i]
            sp["score"] = max(1, min(5, int(item.get("score", 1))))
            sp["reason"] = str(item.get("reason", ""))[:30]
            sp["summary"] = (
                str(item.get("summary", ""))[:100] if sp["score"] >= 3 else ""
            )
        else:
            logger.warning(f"論文 [{i}] のスコアが見つかりません: {paper['title'][:60]}")
            sp["score"] = 1
            sp["reason"] = "スコアなし"
            sp["summary"] = ""
        scored.append(sp)

    usage = response.usage
    usage_dict = {
        "input_tokens": usage.input_tokens,
        "output_tokens": usage.output_tokens,
        "cache_creation_input_tokens": getattr(usage, "cache_creation_input_tokens", 0) or 0,
        "cache_read_input_tokens": getattr(usage, "cache_read_input_tokens", 0) or 0,
    }
    return scored, usage_dict


def score_papers(
    papers: list[dict],
    research_interests: str,
    model: str,
) -> tuple[list[dict], dict]:
    """
    論文リスト全体をスコアリングする。

    Parameters
    ----------
    papers             : fetch_papers() が返した論文リスト
    research_interests : config.yaml の research_interests
    model              : config.yaml の model

    Returns
    -------
    (scored_papers, total_usage)
    """
    if not papers:
        return [], {
            "input_tokens": 0,
            "output_tokens": 0,
            "cache_creation_input_tokens": 0,
            "cache_read_input_tokens": 0,
        }

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise EnvironmentError("ANTHROPIC_API_KEY が設定されていません。")

    client = anthropic.Anthropic(api_key=api_key)
    system_content = _build_system_prompt(research_interests)

    all_scored: list[dict] = []
    total_usage: dict = {
        "input_tokens": 0,
        "output_tokens": 0,
        "cache_creation_input_tokens": 0,
        "cache_read_input_tokens": 0,
    }

    for batch_start in range(0, len(papers), BATCH_SIZE):
        batch = papers[batch_start : batch_start + BATCH_SIZE]
        batch_end = batch_start + len(batch)
        logger.info(
            f"  スコアリング中: {batch_start + 1}〜{batch_end} 件目 / {len(papers)} 件"
        )

        scored_batch, usage = _score_batch(batch, client, system_content, model)
        all_scored.extend(scored_batch)

        if usage:
            for key in total_usage:
                total_usage[key] += usage.get(key, 0)

    return all_scored, total_usage
