"""設定・環境変数の一元管理。"""
import os
from dataclasses import dataclass


@dataclass
class Settings:
    anthropic_api_key: str = os.environ.get("ANTHROPIC_API_KEY", "")
    # J-Quantsは「リフレッシュトークン(7日間有効)→IDトークン(24時間有効)」の
    # 2段階認証。GitHub SecretsにはリフレッシュトークンをJQUANTS_REFRESH_TOKENとして
    # 登録する想定(取得済みのリフレッシュトークンをそのまま使う)。
    jquants_refresh_token: str = os.environ.get("JQUANTS_REFRESH_TOKEN", "")
    notify_webhook_url: str = os.environ.get("NOTIFY_WEBHOOK_URL", "")
    # "slack" (Incoming Webhook, {"text": ...}) または "discord" ({"content": ...})
    notify_webhook_type: str = os.environ.get("NOTIFY_WEBHOOK_TYPE", "slack")

    # コスト管理
    monthly_api_call_limit: int = 300  # 月間のClaude API呼び出し上限(要調整)
    max_consecutive_errors: int = 3    # この回数連続エラーで自動停止

    # 通知の確信度しきい値(この値以上のときだけ通知する)
    notify_confidence_threshold: float = 0.75

    # 出力先
    output_dir: str = "docs"


settings = Settings()
