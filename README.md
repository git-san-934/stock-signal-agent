# stock-signal-agent

日本株の銘柄選定AIエージェント。GitHub Actions上で定期実行し、Googleトレンドの急上昇ワードを起点に上場企業を特定、AI(Claude)が売買シグナルを判定する。

## 特徴

- **銘柄選定方式**: ウォッチリスト監視型ではなく、Googleトレンド急上昇ワード上位から順にチェックし、上場企業に紐づく最初の1件を採用(非上場ならスキップして次の急上昇ワードへ)
- **データソース**: Googleトレンド(pytrends) / Web検索・ニュース(Google News RSS) / 企業公式サイトの月次売上高自主開示(ニュースのベストエフォート検索で代用) / J-Quants API
- **優先度**: 月次売上高開示 > 通常時Googleトレンド > Web検索・ニュース > J-Quants
- **判定方式**: 最初はClaudeに自由判断させ、判定ログ(raw_response含む)を蓄積して後日ルール化する
- **実行タイミング**: 平日 朝7:00 / 昼12:00 / 夕方18:00 (JST)。日本の祝日はスキップ
- **出力**: `docs/` 配下にJSON(判定ごと)+ `index.html`(一覧)を生成し、GitHub Pagesで公開
- **答え合わせ**: 判定の3日後・1週間後の終値と自動突合し、変化率を記録
- **通知**: 確信度がしきい値以上の場合のみ、Slack/Discord互換Webhookで通知(LINE Notifyは2025年3月末で終了済みのため未使用)
- **コスト管理**: `state/usage.json` に月間API呼び出し数・連続エラー数を記録し、上限超過や連続エラー時は自動的に処理をスキップ

## セットアップ

1. リポジトリを作成し、このディレクトリの内容をpush
2. GitHub Secretsに以下を登録
   - `ANTHROPIC_API_KEY`
   - `JQUANTS_REFRESH_TOKEN`(J-Quantsのリフレッシュトークン。7日間で失効するため定期的な更新が必要)
   - `NOTIFY_WEBHOOK_URL`(Slack Incoming WebhookまたはDiscord WebhookのURL)
3. 通知先がDiscordの場合は、GitHub Variables(Settings > Secrets and variables > Actions > Variables)に `NOTIFY_WEBHOOK_TYPE=discord` を追加(未設定時はSlack形式がデフォルト)
4. GitHub Pagesを `docs/` フォルダから公開する設定にする(Settings > Pages)
5. リポジトリの Settings > Actions > General で、ワークフローに書き込み権限(Read and write permissions)を与える(`state/`・`docs/` への自動commitに必要)

## ディレクトリ構成

```
stock-signal-agent/
├── .github/workflows/run.yml   # 定期実行ワークフロー
├── src/
│   ├── main.py                 # エントリーポイント
│   ├── settings.py             # 設定・環境変数読み込み
│   ├── cost_guard.py           # 月間API上限・連続エラー時の自動停止
│   ├── judge.py                # Claudeによる判定ロジック・JSONパース
│   ├── notify.py                # 通知処理(Slack/Discord Webhook)
│   ├── backtest.py             # 判定の答え合わせ(3日後・1週間後の株価突合)
│   ├── report.py               # docs/index.html の生成
│   └── data_sources/
│       ├── google_trends.py    # Googleトレンド取得
│       ├── news_search.py      # ニュース検索・月次開示チェック(Google News RSS)
│       └── jquants.py          # J-Quants API連携
├── docs/                        # 出力(JSON/HTML) → GitHub Pages
├── state/                       # コスト管理用の永続データ(usage.json)
└── requirements.txt
```

## 実装状況

- [x] Googleトレンド急上昇ワード取得(pytrends)
- [x] 急上昇ワード→上場企業の紐付け(単純部分一致。精度は実運用しながらログを見て調整予定)
- [x] J-Quants APIクライアント(認証・株価・財務データ・特定日終値の取得)
- [x] ニュース検索・月次売上高開示チェック(Google News RSSベースのベストエフォート)
- [x] Claude判定プロンプト・JSONパース(不正フォーマット時は「様子見」にフォールバック、raw_responseは常に保持)
- [x] 答え合わせ機能(3日後・1週間後の株価突合、docs/配下のJSONに追記)
- [x] 通知ロジック(確信度がしきい値以上の場合のみSlack/Discord Webhookで送信)
- [x] 日本の祝日判定(jpholidayで祝日をスキップ)
- [x] コスト管理(月間API呼び出し上限・連続エラー時の自動停止、state/usage.jsonに記録)

## 既知の制約・今後の調整ポイント

- 急上昇ワード→企業名の紐付けは単純な部分一致のため、無関係な一般語と誤ヒットする可能性がある。判定ログを見ながら精度を調整する方針。
- 月次売上高の自主開示チェックはニュース記事のタイトルに「月次」が含まれるかで代用しており、企業公式サイトを直接巡回しているわけではない。
- 答え合わせのために取得する株価は判定当日の`daily_quotes`最新終値を基準(baseline_price)としている。
