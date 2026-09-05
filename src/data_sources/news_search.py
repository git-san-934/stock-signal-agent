"""急上昇ワードに関連するニュース・Web情報を取得する。

外部APIキー不要のGoogle News RSSフィード(https://news.google.com/rss/search)を
利用する。公式の検索APIではないため、将来的にフォーマットが変わる可能性がある点に注意。
"""
import urllib.parse
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional

import requests

_RSS_BASE = "https://news.google.com/rss/search"


def _fetch_rss(query: str, limit: int) -> List[Dict]:
    """Google News RSSフィードを取得し、記事情報のリストにパースする共通処理。"""
    params = {"q": query, "hl": "ja", "gl": "JP", "ceid": "JP:ja"}
    url = f"{_RSS_BASE}?{urllib.parse.urlencode(params)}"

    resp = requests.get(url, timeout=30)
    resp.raise_for_status()

    root = ET.fromstring(resp.content)
    articles = []
    for item in root.findall("./channel/item")[:limit]:
        articles.append({
            "title": item.findtext("title", default=""),
            "url": item.findtext("link", default=""),
            "published": item.findtext("pubDate", default=""),
            "source": item.findtext("source", default=""),
        })
    return articles


def search_news(keyword: str, limit: int = 5) -> List[Dict]:
    """キーワードに関連する直近ニュースを取得する。

    Returns:
        記事情報のリスト(タイトル・URL・公開日・情報源)
    """
    return _fetch_rss(keyword, limit)


def check_monthly_sales_disclosure(company_name: str, limit: int = 5) -> Optional[Dict]:
    """企業の月次売上高等の自主開示に関する直近ニュースがないか確認する。

    企業公式サイトのIRページを個別に巡回する仕組みは会社ごとに構造が異なり
    一般化が難しいため、簡易的にニュース記事のタイトルに「月次」を含むものを
    検索して代用する(ベストエフォート)。ヒットしなければ None を返す。

    Returns:
        最も新しい該当記事の情報。該当なしなら None。
    """
    articles = _fetch_rss(f"{company_name} 月次売上高", limit)
    for article in articles:
        if "月次" in article["title"]:
            return article
    return None
