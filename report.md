# 検証レポート（apps-rag-simple）

作成日: 2026-03-04

## 1. 今回の確認結果（最新）

- API疎通: `test_api.py --base-url https://apps-ketana-ext-rag-simple.azurewebsites.net` は `/health` と `/api/search` ともに PASS。
- コード状態: `main.py` の手動計装呼び出しはコメントアウト状態（`# setup_telemetry(app)`）。
- テレメトリ（直近15分）:
  - `AppRequests`: 0
  - `AppDependencies`: 0

注記: テレメトリは取り込み遅延の影響を受けるため、即時 0 の場合は 5〜15 分待って再確認が必要。

## 2. これまでの検証パターン一覧

### パターンA: ローカル静的確認
- 目的: 構文エラーや import エラーの早期検知
- 実行例:
  - `python -m compileall app`
  - `python -m compileall test_api.py`
- 判定基準: compile 成功（エラーなし）

### パターンB: APIスモークテスト（ローカル/本番）
- 目的: `/health` と `/api/search` の回帰検知
- 実行例:
  - `python test_api.py --base-url http://127.0.0.1:8000`
  - `python test_api.py --base-url https://apps-ketana-ext-rag-simple.azurewebsites.net`
- 判定基準:
  - `/health` が PASS
  - `/api/search` が PASS
  - `source` が許容値（`placeholder-rag` / `azure-search-semantic` / `azure-search-semantic-hybrid` / `rag+aoai`）

### パターンC: App Service設定確認
- 目的: 接続先不一致・観測漏れの切り分け
- 実行例:
  - `az webapp config appsettings list -g <rg> -n <app>`
- 主な確認項目:
  - `APPLICATIONINSIGHTS_CONNECTION_STRING`
  - `APPINSIGHTS_INSTRUMENTATIONKEY`
  - `XDT_MicrosoftApplicationInsights_*`

### パターンD: デプロイ確認
- 目的: 変更反映漏れ防止
- 実行例:
  - ZIP化: `app/`, `requirements.txt`, `Procfile`
  - `az webapp deploy --type zip --restart true`
- 判定基準: `RuntimeSuccessful` + スモークテスト PASS

### パターンE: テレメトリ確認（Log Analytics）
- 目的: 自動収集の実態確認（workspace-based AI）
- 実行例:
  - `AppRequests | where TimeGenerated > ago(15m) | summarize count()`
  - `AppDependencies | where TimeGenerated > ago(15m) | summarize count()`
- 判定基準:
  - 目的に応じて `AppRequests` / `AppDependencies` の増減を確認

### パターンF: 旧明示スパン痕跡チェック
- 目的: 明示OTel送信停止の確認
- 実行例:
  - `union isfuzzy=true AppTraces,AppDependencies | where ... has 'aoai.responses.call' | summarize count()`
- 判定基準: `count() = 0`

## 3. 主要な切り分け知見

1) App Insights の接続先不一致があると、正常稼働でも観測できない。
2) Linux App Service + Python では、設定組み合わせにより `requests` が入らず `dependencies` のみ増えるケースがある。
3) 収集の確認は「トラフィック生成 → 数分待機 → 再クエリ」を1セットで行う。
4) Push Protection（secret scanning）により、ドキュメント内キーでも push が拒否される。

## 4. 再実行用クイックチェック手順

1. `python -m compileall app`
2. `python test_api.py --base-url https://apps-ketana-ext-rag-simple.azurewebsites.net`
3. Log Analyticsで以下2本を実行
   - `AppRequests` 直近15分 count
   - `AppDependencies` 直近15分 count
4. 必要に応じて 5〜15 分待って再クエリ

## 5. 現時点の状態まとめ

- アプリ機能（検索API）は正常。
- 手動計装呼び出しはコメントアウト。
- 最新確認ではテレメトリは 15 分窓で 0/0（要再観測）。
