"""docs/配下の判定結果一覧をHTMLとして出力する(GitHub Pages公開用)。"""
import datetime
import json
from pathlib import Path
from typing import Dict, List


def _load_all_records(output_dir: Path) -> List[Dict]:
    records = []
    for path in sorted(output_dir.glob("*.json"), reverse=True):
        try:
            with open(path, "r", encoding="utf-8") as f:
                records.append(json.load(f))
        except (json.JSONDecodeError, OSError):
            continue
    return records


def _fmt_change(backtest: Dict, key: str) -> str:
    entry = backtest.get(key)
    if not entry or entry.get("change_pct") is None:
        return "-"
    return f"{entry['change_pct']:+.2f}%"


def _render_row(record: Dict) -> str:
    company = record.get("company") or {}
    result = record.get("result") or {}
    backtest = record.get("backtest") or {}
    confidence = result.get("confidence", 0) or 0

    return (
        "<tr>"
        f"<td>{record.get('date', '')}</td>"
        f"<td>{company.get('name', '')}({company.get('code', '')})</td>"
        f"<td>{result.get('verdict', '')}</td>"
        f"<td>{confidence:.2f}</td>"
        f"<td>{result.get('reason', '')}</td>"
        f"<td>{_fmt_change(backtest, 'after_3d')}</td>"
        f"<td>{_fmt_change(backtest, 'after_7d')}</td>"
        "</tr>"
    )


def generate_index_html(output_dir: Path) -> None:
    """docs/index.html を生成する。"""
    records = _load_all_records(output_dir)
    rows = "\n    ".join(_render_row(r) for r in records)

    html = f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<title>stock-signal-agent 判定履歴</title>
<style>
  body {{ font-family: sans-serif; margin: 2rem; }}
  table {{ border-collapse: collapse; width: 100%; }}
  th, td {{ border: 1px solid #ccc; padding: 0.5rem; text-align: left; font-size: 0.9rem; }}
  th {{ background: #f0f0f0; }}
</style>
</head>
<body>
<h1>stock-signal-agent 判定履歴</h1>
<p>最終更新: {datetime.date.today().isoformat()}</p>
<table>
  <thead>
    <tr>
      <th>日付</th><th>銘柄</th><th>判定</th><th>確信度</th><th>理由</th>
      <th>3日後</th><th>1週間後</th>
    </tr>
  </thead>
  <tbody>
    {rows}
  </tbody>
</table>
</body>
</html>
"""

    (output_dir / "index.html").write_text(html, encoding="utf-8")
