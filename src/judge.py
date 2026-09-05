"""収集した情報をもとにClaudeに売買シグナルを判定させる。

方針: 最初はルールを固めず、Claudeに自由に判断させる。
判定結果(理由・確信度を含む)をログとして蓄積し、後日そのログを見て
ルール化・プロンプト改善を行う。
"""
import json
import re
from typing import Dict, Optional

from anthropic import Anthropic

from .settings import settings

SYSTEM_PROMPT = """\
あなたは日本株の銘柄選定を支援するアナリストです。
与えられた企業の情報(株価・財務データ、ニュース・トレンド情報、
月次売上高等の自主開示があればその内容)をもとに、
その銘柄について「買い候補」「様子見」「対象外」のいずれかを判定してください。

出力は以下のJSON形式のみで、それ以外のテキストは含めないでください:
{
  "verdict": "買い候補" | "様子見" | "対象外",
  "confidence": 0.0から1.0の数値,
  "reason": "判定理由を簡潔に(日本語)"
}
"""

_VALID_VERDICTS = {"買い候補", "様子見", "対象外"}


def _extract_text(response) -> str:
    """APIレスポンスからテキストブロックを連結して取り出す。"""
    return "".join(
        block.text for block in response.content if getattr(block, "type", None) == "text"
    )


def _parse_json_block(raw_text: str) -> Optional[Dict]:
    """Claudeの出力からJSONオブジェクトを取り出す。

    指示通りJSON単体で返ってくる想定だが、念のため
    ```json ... ``` のようなコードフェンスが付いていても対応する。
    """
    cleaned = raw_text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # 前後に余計な文章が混ざっている場合、最初の { から最後の } までを抜き出して再挑戦
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return None

    return None


def judge_signal(company_info: Dict) -> Dict:
    """企業情報を渡してClaudeに判定させる。

    Args:
        company_info: 証券コード、株価・財務データ、ニュース・トレンド情報等をまとめた辞書

    Returns:
        判定結果の辞書。常に以下のキーを含む:
        - verdict: "買い候補" | "様子見" | "対象外"
        - confidence: 0.0〜1.0
        - reason: 判定理由
        - raw_response: Claudeの生の応答テキスト(後日ルール化する際の分析用にログとして保持)
        - parse_error: JSONパースに失敗しフォールバックした場合 True
    """
    client = Anthropic(api_key=settings.anthropic_api_key)

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=500,
        system=SYSTEM_PROMPT,
        messages=[
            {"role": "user", "content": str(company_info)}
        ],
    )

    raw_text = _extract_text(response)
    parsed = _parse_json_block(raw_text)

    if not parsed or parsed.get("verdict") not in _VALID_VERDICTS:
        # パース失敗、または想定外のverdict値の場合は安全側(様子見)にフォールバック。
        # raw_responseは必ず残すので、後日ログを見てプロンプト改善に使える。
        return {
            "verdict": "様子見",
            "confidence": 0.0,
            "reason": "Claudeの応答をJSONとして解析できなかったため、安全側で様子見としました。",
            "raw_response": raw_text,
            "parse_error": True,
        }

    try:
        confidence = float(parsed.get("confidence", 0.0))
    except (TypeError, ValueError):
        confidence = 0.0
    confidence = max(0.0, min(1.0, confidence))

    return {
        "verdict": parsed["verdict"],
        "confidence": confidence,
        "reason": str(parsed.get("reason", "")),
        "raw_response": raw_text,
        "parse_error": False,
    }
