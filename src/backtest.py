"""判定の答え合わせ: 3日後・1週間後の実株価と自動突合する。

docs/配下に蓄積された過去の判定レコード(JSON)を走査し、
判定日から3日後・1週間後の終値が取得できるようになったものについて、
判定時点の株価(baseline_price)と比較した変化率をレコードに追記する。
"""
import datetime
import json
from pathlib import Path
from typing import Dict, Iterator, Tuple

from .data_sources.jquants import JQuantsClient

_HORIZONS = ((3, "after_3d"), (7, "after_7d"))


def _iter_records(output_dir: Path) -> Iterator[Tuple[Path, Dict]]:
    for path in sorted(output_dir.glob("*.json")):
        try:
            with open(path, "r", encoding="utf-8") as f:
                yield path, json.load(f)
        except (json.JSONDecodeError, OSError):
            continue


def run_backtest(output_dir: Path, jquants: JQuantsClient) -> None:
    """まだ答え合わせが済んでいない過去レコードを埋める。

    対象日がまだ来ていない場合や、対象日が非営業日でデータが
    取得できない場合はスキップし、次回の実行時に再挑戦する。
    """
    today = datetime.date.today()

    for path, record in _iter_records(output_dir):
        try:
            decision_date = datetime.date.fromisoformat(record["date"])
        except (KeyError, ValueError):
            continue

        company = record.get("company") or {}
        code = company.get("code")
        baseline = record.get("baseline_price")
        if not code:
            continue

        record.setdefault("backtest", {})
        changed = False

        for horizon_days, key in _HORIZONS:
            if key in record["backtest"]:
                continue

            check_date = decision_date + datetime.timedelta(days=horizon_days)
            if check_date > today:
                continue  # まだその日が来ていない

            actual = jquants.get_close_price_on(code, check_date.isoformat())
            if actual is None:
                continue  # 非営業日等でデータ未取得。次回また試す

            change_pct = None
            if baseline:
                change_pct = round((actual - baseline) / baseline * 100, 2)

            record["backtest"][key] = {
                "check_date": check_date.isoformat(),
                "price": actual,
                "change_pct": change_pct,
            }
            changed = True

        if changed:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(record, f, ensure_ascii=False, indent=2)
