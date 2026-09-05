"""Googleトレンドの急上昇ワードを取得する。

pytrends (非公式ライブラリ) の日次トレンド機能を利用して、
日本の急上昇ワードランキングを上位から順に取得する。
急上昇ワードには一般ワードも含まれるため、上場企業名・銘柄との紐付けは
data_sources/jquants.py の get_company_by_keyword() 側で行う。
"""
from typing import List

from pytrends.request import TrendReq


def get_trending_words(limit: int = 20) -> List[str]:
    """急上昇ワードを上位から順に返す。

    Args:
        limit: 取得する最大件数

    Returns:
        急上昇ワードのリスト(順位順、先頭が最も注目度が高い)
    """
    pytrends = TrendReq(hl="ja-JP", tz=540)  # tz=540 は JST (UTC+9) 分
    df = pytrends.trending_searches(pn="japan")

    # df は1列のDataFrame(列名は数値の0)。上から順に急上昇ワードが並んでいる。
    words = df[0].tolist()
    return words[:limit]
