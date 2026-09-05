"""コスト管理: 月間API呼び出し上限・連続エラー時の自動停止を管理する。

GitHub Actionsは毎回新しいプロセスで実行され状態を保持しないため、
リポジトリ内のJSONファイル(state/usage.json)に呼び出し回数・連続エラー数を
記録し、ワークフロー側でcommitして次回実行時に引き継ぐ。
"""
import datetime
import json
from pathlib import Path
from typing import Dict

from .settings import settings

STATE_PATH = Path("state/usage.json")

_DEFAULT_STATE = {"month": "", "api_calls": 0, "consecutive_errors": 0}


def _current_month() -> str:
    return datetime.date.today().strftime("%Y-%m")


def load_state() -> Dict:
    """状態を読み込む。月が変わっていたら呼び出し回数だけリセットする。

    連続エラー数は月をまたいでも維持する(自動停止は手動で気づいて
    対応するまで解除されない方が安全なため)。
    """
    if not STATE_PATH.exists():
        state = dict(_DEFAULT_STATE)
        state["month"] = _current_month()
        return state

    try:
        with open(STATE_PATH, "r", encoding="utf-8") as f:
            state = json.load(f)
    except (json.JSONDecodeError, OSError):
        state = dict(_DEFAULT_STATE)

    if state.get("month") != _current_month():
        state["month"] = _current_month()
        state["api_calls"] = 0

    return state


def save_state(state: Dict) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def should_skip() -> bool:
    """月間上限超過、または連続エラーが多い場合はTrue(=このrunをスキップすべき)。"""
    state = load_state()
    if state["api_calls"] >= settings.monthly_api_call_limit:
        return True
    if state["consecutive_errors"] >= settings.max_consecutive_errors:
        return True
    return False


def record_success() -> None:
    """Claude API呼び出しが成功した場合に呼ぶ。連続エラー数をリセットする。"""
    state = load_state()
    state["api_calls"] += 1
    state["consecutive_errors"] = 0
    save_state(state)


def record_error() -> None:
    """Claude API呼び出し(または一連の処理)が失敗した場合に呼ぶ。"""
    state = load_state()
    state["api_calls"] += 1
    state["consecutive_errors"] += 1
    save_state(state)
