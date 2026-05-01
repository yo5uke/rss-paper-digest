"""
config_loader.py: config.yaml を読み込み、設定値を dataclass で提供します。
"""

from dataclasses import dataclass, field
from pathlib import Path

import yaml

CONFIG_FILE = Path("config.yaml")
DEFAULT_MODEL = "claude-sonnet-4-6"


@dataclass
class Config:
    feeds: list[str]
    research_interests: str
    max_papers_per_feed: int = 10
    model: str = DEFAULT_MODEL


def load_config(path: Path = CONFIG_FILE) -> Config:
    """
    config.yaml を読み込んで Config を返す。

    Raises
    ------
    FileNotFoundError : config.yaml が存在しない場合
    ValueError        : 必須キーが欠けている場合
    """
    if not path.exists():
        raise FileNotFoundError(
            f"{path} が見つかりません。\n"
            "  cp config.example.yaml config.yaml\n"
            "を実行して config.yaml を作成してください。"
        )

    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict):
        raise ValueError("config.yaml の形式が不正です。")

    feeds: list[str] = data.get("feeds", [])
    if not feeds:
        raise ValueError("config.yaml に feeds が設定されていません。")

    research_interests: str = str(data.get("research_interests", "")).strip()
    if not research_interests:
        raise ValueError("config.yaml に research_interests が設定されていません。")

    return Config(
        feeds=[str(f).strip() for f in feeds if f],
        research_interests=research_interests,
        max_papers_per_feed=int(data.get("max_papers_per_feed", 10)),
        model=str(data.get("model", DEFAULT_MODEL)),
    )
