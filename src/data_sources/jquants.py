"""J-Quants APIから株価・財務データを取得する。

認証は「リフレッシュトークン(7日間有効)→IDトークン(24時間有効)」の
2段階方式。呼び出しごとにIDトークンを都度取得し直す(GitHub Actionsは
毎回新しいプロセスで実行されるためキャッシュは持たない)。

参考: https://jpx.gitbook.io/j-quants-en/
"""
import re
from typing import Dict, List, Optional

import requests

BASE_URL = "https://api.jquants.com/v1"

# 会社名からの単純マッチングを補助するために除去する法人格等の接尾辞・接頭辞
_CORP_SUFFIXES = ["株式会社", "(株)", "有限会社", "(有)"]


def _strip_corp_suffix(name: str) -> str:
    cleaned = name
    for suffix in _CORP_SUFFIXES:
        cleaned = cleaned.replace(suffix, "")
    return cleaned.strip()


class JQuantsClient:
    def __init__(self, refresh_token: str):
        self.refresh_token = refresh_token
        self._id_token: Optional[str] = None
        self._listed_info_cache: Optional[List[Dict]] = None

    def _get_id_token(self) -> str:
        """リフレッシュトークンからIDトークンを取得する。"""
        if self._id_token:
            return self._id_token

        resp = requests.post(
            f"{BASE_URL}/token/auth_refresh",
            params={"refreshtoken": self.refresh_token},
            timeout=30,
        )
        resp.raise_for_status()
        self._id_token = resp.json()["idToken"]
        return self._id_token

    def _get(self, path: str, params: Optional[Dict] = None) -> Dict:
        headers = {"Authorization": f"Bearer {self._get_id_token()}"}
        resp = requests.get(f"{BASE_URL}{path}", headers=headers, params=params, timeout=30)

        if resp.status_code == 401:
            # IDトークンの有効期限切れの可能性があるため1回だけ再取得してリトライ
            self._id_token = None
            headers = {"Authorization": f"Bearer {self._get_id_token()}"}
            resp = requests.get(f"{BASE_URL}{path}", headers=headers, params=params, timeout=30)

        resp.raise_for_status()
        return resp.json()

    def _load_listed_info(self) -> List[Dict]:
        """上場銘柄一覧を取得する(プロセス内でキャッシュ)。"""
        if self._listed_info_cache is None:
            data = self._get("/listed/info")
            self._listed_info_cache = data.get("info", [])
        return self._listed_info_cache

    def get_company_by_keyword(self, keyword: str) -> Optional[Dict]:
        """キーワード(急上昇ワード)が上場企業名に一致するか調べる。

        単純な部分一致(キーワードが会社名を含む、または会社名がキーワードを含む)
        でマッチングする。法人格の接尾辞(株式会社等)は除去して比較する。
        複数一致した場合は最初の1件を返す。

        Returns:
            一致した企業情報({"code": 証券コード, "name": 会社名, ...})。
            一致しなければ None。
        """
        keyword_clean = _strip_corp_suffix(keyword)
        if not keyword_clean:
            return None

        for company in self._load_listed_info():
            name = company.get("CompanyName", "")
            name_clean = _strip_corp_suffix(name)
            if not name_clean:
                continue

            if name_clean in keyword_clean or keyword_clean in name_clean:
                return {
                    "code": company.get("Code"),
                    "name": name,
                    "sector": company.get("Sector33CodeName"),
                    "market": company.get("MarketCodeName"),
                }

        return None

    def get_price_and_financials(self, company_code: str) -> Dict:
        """株価・財務データを取得する。

        株価は直近の日足(daily_quotes)、財務情報は決算短信サマリー(statements)を
        それぞれ取得して結合する。
        """
        prices = self._get("/prices/daily_quotes", params={"code": company_code})
        statements = self._get("/fins/statements", params={"code": company_code})

        return {
            "code": company_code,
            "daily_quotes": prices.get("daily_quotes", []),
            "statements": statements.get("statements", []),
        }

    def get_close_price_on(self, company_code: str, date: str) -> Optional[float]:
        """特定日の終値を取得する(答え合わせ機能用)。

        Args:
            company_code: 証券コード
            date: "YYYY-MM-DD" 形式の日付

        Returns:
            終値。該当日にデータがない(非営業日等)場合は None。
        """
        data = self._get("/prices/daily_quotes", params={"code": company_code, "date": date})
        quotes = data.get("daily_quotes", [])
        if not quotes:
            return None
        close = quotes[0].get("Close")
        return float(close) if close is not None else None
