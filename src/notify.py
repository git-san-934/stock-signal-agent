"""高確信度の判定が出たときだけ通知する。

LINE Notifyは2025年3月末でサービス終了しているため、Slack Incoming Webhook /
Discord Webhookのいずれかに対応した汎用実装にしている。
"""
from typing import Dict

import requests

from .settings import settings


def _build_message(company_code: str, result: Dict) -> str:
    verdict = result.get("verdict", "不明")
    confidence = result.get("confidence", 0)
    reason = result.get("reason", "")
    return (
        f"【株シグナル通知】{company_code}\n"
        f"判定: {verdict}(確信度 {confidence:.2f})\n"
        f"理由: {reason}"
    )


def notify_if_confident(company_code: str, result: Dict) -> None:
    """確信度がしきい値以上の場合のみ通知を送る。

    Args:
        company_code: 証券コード
        result: judge.judge_signal() の戻り値
    """
    if result.get("confidence", 0) < settings.notify_confidence_threshold:
        return

    if not settings.notify_webhook_url:
        print("NOTIFY_WEBHOOK_URLが未設定のため通知をスキップしました。")
        return

    message = _build_message(company_code, result)

    if settings.notify_webhook_type == "discord":
        payload = {"content": message}
    else:
        # Slack Incoming Webhook形式(デフォルト)
        payload = {"text": message}

    resp = requests.post(settings.notify_webhook_url, json=payload, timeout=30)
    resp.raise_for_status()
