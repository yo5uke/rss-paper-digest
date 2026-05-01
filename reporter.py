"""
reporter.py: スコア済み論文リストから Markdown ダイジェストを生成します。
"""

from pathlib import Path

_HIGH_SCORE_SECTIONS: list[tuple[int, str, str]] = [
    (5, "⭐⭐⭐⭐⭐ 必読", "score: 5"),
    (4, "⭐⭐⭐⭐ 読む価値あり", "score: 4"),
    (3, "⭐⭐⭐ 参考程度", "score: 3"),
]

_LOW_SCORE_HEADER = "⭐⭐ スキップ推奨（score: 1-2）"


def generate_report(papers: list[dict], today: str, output_path: Path) -> None:
    """
    スコア済み論文リストを Markdown ファイルとして出力する。

    Parameters
    ----------
    papers      : score / reason / summary が付いた論文リスト
    today       : 日付文字列（YYYY-MM-DD）
    output_path : 出力先パス（例: output/2026-04-28.md）
    """
    sorted_papers = sorted(papers, key=lambda p: p.get("score", 0), reverse=True)

    lines: list[str] = [f"# 📚 Paper Digest — {today}", ""]

    for score, section_title, score_label in _HIGH_SCORE_SECTIONS:
        matching = [p for p in sorted_papers if p.get("score") == score]
        if not matching:
            continue

        lines.append(f"## {section_title}（{score_label}）")
        lines.append("")

        for paper in matching:
            lines.append(f"**[{paper['journal']}] {paper['title']}**")
            if paper.get("summary"):
                lines.append(f"📝 {paper['summary']}")
            lines.append(f"💡 {paper.get('reason', '')}")
            lines.append(f"🔗 {paper['url']}")
            lines.append("")

    low_score_papers = [p for p in sorted_papers if p.get("score", 0) <= 2]
    if low_score_papers:
        lines.append(f"## {_LOW_SCORE_HEADER}")
        lines.append("")
        for paper in low_score_papers:
            reason = paper.get("reason", "")
            reason_text = f"（{reason}）" if reason else ""
            lines.append(f"- [{paper['journal']}] {paper['title']}{reason_text}")
        lines.append("")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")
