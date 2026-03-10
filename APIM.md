# App Service を APIM に登録する手順

この手順は、既存の App Service API（FastAPI）を Azure API Management (APIM) に登録するための実運用向け手順です。

重要:
- APIM に登録する対象は **RAGアプリのAPI（App Service）** です。
- Azure OpenAI エンドポイント自体（`*.openai.azure.com`）を直接 APIM 登録する手順ではありません。
- 本アプリは APIM -> App Service ->（アプリ内部で）Azure OpenAI 呼び出し、という経路になります。

対象アプリ:
- App Service: https://apps-ketana-ext-rag-simple.azurewebsites.net
- OpenAPI URL: https://apps-ketana-ext-rag-simple.azurewebsites.net/openapi.json

---

## 1. 事前準備

1. Azure Portal で APIM インスタンスが作成済みであることを確認
2. App Service が外部から `GET /openapi.json` を返せることを確認
3. Azure CLI を使う場合はログイン

```powershell
az login
az account show
```

---

## 2. Portal で登録（推奨・最短）

1. Azure Portal で対象 APIM を開く
2. 左メニュー「APIs」→「+ Add API」
3. 「OpenAPI」を選択
4. 入力値を設定
   - OpenAPI specification: Link
   - OpenAPI link: `https://apps-ketana-ext-rag-simple.azurewebsites.net/openapi.json`
   - Display name: `apps-rag-simple`
   - Name: `apps-rag-simple`
   - API URL suffix: `rag-simple`
5. Create を実行

これで APIM の公開 URL は以下の形になります。
- `https://<your-apim-name>.azure-api.net/rag-simple/...`

例:
- `POST https://<your-apim-name>.azure-api.net/rag-simple/api/search`
- `GET  https://<your-apim-name>.azure-api.net/rag-simple/health`

---

## 3. Product への紐付け（外部利用する場合）

1. APIM の API 画面で登録した `apps-rag-simple` を開く
2. 「Settings」→「Products」で `Starter` などに追加
3. サブスクリプションキー必須にする場合は Product 側で有効化

メモ:
- 内部用途のみならキー不要運用でも可
- 外部公開するならキー必須 + レート制限を推奨

---

## 4. APIM 経由の動作確認

### 4.1 Portal の Test タブ

1. APIM の対象 API → `POST /api/search`
2. Request body:

```json
{
  "query": "RAGとは何か"
}
```

3. `200` とレスポンス本文を確認

### 4.2 ローカルから実行

```powershell
$apim='https://<your-apim-name>.azure-api.net'
$subKey='<your-subscription-key>'
$body=@{query='RAGとは何か'}|ConvertTo-Json

Invoke-RestMethod -Method Post `
  -Uri "$apim/rag-simple/api/search" `
  -Headers @{ 'Ocp-Apim-Subscription-Key' = $subKey } `
  -ContentType 'application/json' `
  -Body $body
```

---

## 5. 追加推奨設定（本番向け）

1. Rate limit ポリシーを API または Product に追加
2. 必要なら IP 制限、CORS、JWT 検証を追加
3. バックエンド保護のため、App Service 側を APIM 経由アクセス中心に制御

---

## 6. よくあるハマりどころ

1. `openapi.json` が APIM から取得できず import 失敗
   - App Service 側で URL 到達性を確認
   - 取得できても `openapi: 3.1.0` の場合、APIM 側で "Please specify valid OpenAPI specification file." になることがあります
   - この場合はアプリ側を `openapi_version=\"3.0.3\"` で再デプロイして再実施
2. API URL suffix が重複して作成失敗
   - 別 suffix を指定（例: `rag-simple-v2`）
3. Test は成功するがクライアント実行が 401/403
   - Subscription Key の付与漏れを確認
4. APIM 経由でタイムアウト
   - APIM のタイムアウト・バックエンド応答時間を確認

---

## 7. CLI で最小作成（任意）

既存 APIM に API を登録する例です。

```powershell
$rg='rg-ketana-ext-eastus2'
$apim='<your-apim-name>'

az apim api import \
  --resource-group $rg \
  --service-name $apim \
  --api-id apps-rag-simple \
  --path rag-simple \
  --specification-format OpenApiJson \
  --specification-url 'https://apps-ketana-ext-rag-simple.azurewebsites.net/openapi.json'
```

---

## 8. 最短チェックリスト

- [ ] `openapi.json` をブラウザ/CLIで取得できる
- [ ] APIM に OpenAPI import 完了
- [ ] `POST /rag-simple/api/search` が 200
- [ ] Product / Subscription Key 方針を決定
- [ ] レート制限ポリシーを設定
