"""stock-signal-agent エントリーポイント。

処理の流れ:
1. 祝日チェック(祝日ならスキップして終了)
2. コスト管理チェック(月間API呼び出し上限・連続エラー数を確認)
3. Googleトレンド急上昇ワードを取得
4. 上位ワードから順に上場企業と紐付け、最初の1件を採用
5. 月次売上高開示 > Googleトレンド > ニュース > J-Quants の優先度でデータ収集
6. Claudeに判定させる
7. 確信度が高ければ通知
8. 結果をdocs/にJSON/HTML出力してGitHub Pagesに反映
9. 過去の判定の答え合わせ(3日後・1週間後の実株価と突合)
"""
import datetime
import json
import sys
from pathlib import Path
from typing import Optional

import jpholiday

from . import cost_guard, report
from .settings import settings
from .data_sources.google_trends import get_trending_words
from .data_sources.jquants import JQuantsClient
from .data_sources import news_search
from .judge import judge_signal
from .notify import notify_if_confident
from .backtest import run_backtest


def is_market_day(today: datetime.date) -> bool:
    """土日・日本の祝日でなければ True。"""
    if today.weekday() >= 5:  # 5=土, 6=日
        return False
    if jpholiday.is_holiday(today):
        return False
    return True


def _extract_latest_close(daily_quotes) -> Optional[float]:
    """daily_quotesの中から最新日の終値を取り出す(判定時点の基準株価として保存する)。"""
    if not daily_quotes:
        return None
    latest = sorted(daily_quotes, key=lambda q: q.get("Date", ""))[-1]
    close = latest.get("Close")
    return float(close) if close is not None else None


def run() -> None:
    today = datetime.date.today()
    output_dir = Path(settings.output_dir)
    output_dir.mkdir(exist_ok=True)

    jquants = JQuantsClient(refresh_token=settings.jquants_refresh_token)

    # 答え合わせは市場が休みの日でも(前回までの分を)進めておく
    run_backtest(output_dir, jquants)

    if not is_market_day(today):
        print(f"{today} is not a market day. Skipping new signal generation.")
        report.generate_index_html(output_dir)
        return

    if cost_guard.should_skip():
        print("Cost guard triggered (monthly limit or consecutive errors). Skipping this run.")
        report.generate_index_html(output_dir)
        return

    trending_words = get_trending_words()

    selected_company = None
    for word in trending_words:
        company = jquants.get_company_by_keyword(word)
        if company:
            selected_company = company
            break

    if not selected_company:
        print("No listed company matched today's trending words.")
        report.generate_index_html(output_dir)
        return

    # 優先度: 月次売上高開示 > Googleトレンド > ニュース > J-Quants
    disclosure = news_search.check_monthly_sales_disclosure(selected_company["name"])
    news = news_search.search_news(selected_company["name"])
    financials = jquants.get_price_and_financials(selected_company["code"])

    company_info = {
        "company": selected_company,
        "monthly_disclosure": disclosure,
        "news": news,
        "financials": financials,
    }

    try:
        result = judge_signal(company_info)
        cost_guard.record_success()
    except Exception as e:  # noqa: BLE001 — Claude呼び出し失敗時もrunを継続させるため広めに捕捉
        cost_guard.record_error()
        print(f"Claude判定でエラーが発生しました: {e}", file=sys.stderr)
        report.generate_index_html(output_dir)
        return

    notify_if_confident(selected_company["code"], result)

    record = {
        "date": today.isoformat(),
        "company": selected_company,
        "baseline_price": _extract_latest_close(financials.get("daily_quotes", [])),
        "result": result,
    }
    with open(output_dir / f"{today.isoformat()}.json", "w", encoding="utf-8") as f:
        json.dump(record, f, ensure_ascii=False, indent=2)

    report.generate_index_html(output_dir)


if __name__ == "__main__":
    run()
