# apps-rag-simple

RAG検索アプリのAPI専用MVPです。

- RAG検索: プレースホルダ実装
- 回答生成: Azure OpenAI Responses API
- 認証: Microsoft Entra ID（`DefaultAzureCredential`）
- デプロイ先: Azure App Service（`apps-ketana-ext-rag-simple`）

## ローカル実行

### 0) `.env` 設定
プロジェクトルートの `.env` を編集して AOAI 設定値を入れてください。

### 1) 依存関係インストール
```powershell
c:/vscodepy/apps-rag-simple/.venv/Scripts/python.exe -m pip install -r requirements.txt
```

### 2) API起動
```powershell
c:/vscodepy/apps-rag-simple/.venv/Scripts/python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

### 3) ヘルスチェック
```powershell
Invoke-RestMethod -Method Get -Uri http://127.0.0.1:8000/health
```

### 4) 検索API呼び出し
```powershell
$body = @{ query = 'RAGとは何か' } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/search -ContentType 'application/json' -Body $body
```

## 環境変数

`.env.example` を `.env` にコピーして利用してください。

```text
LOG_LEVEL=INFO
AZURE_OPENAI_ENDPOINT=https://<your-resource>.openai.azure.com/openai/v1/
AZURE_OPENAI_DEPLOYMENT_NAME=<your-deployment-name>
AOAI_MAX_TOKENS=400
AZURE_OPENAI_EMBEDDING_MODEL=text-embedding-3-large
AZURE_SEARCH_ENDPOINT=https://<your-search-service>.search.windows.net
AZURE_SEARCH_INDEX_NAME=<your-index-name>
AZURE_SEARCH_API_KEY=<your-search-api-key>
AZURE_SEARCH_VECTOR_FIELD=contentVector
AZURE_SEARCH_SEMANTIC_CONFIG=<your-semantic-config-name>
```

## API仕様（MVP）
- `POST /api/search`
	- request: `{ "query": "..." }`
	- response: `query`, `results`, `answer`, `source`
- `GET /health`
	- response: `{ "status": "ok" }`

## AOAI連携（回答生成）
- `POST /api/search` は、RAGプレースホルダの検索結果を作成した後に Azure OpenAI で回答生成を試行します。
- 認証は Microsoft Entra ID（`DefaultAzureCredential`）を使用します。
- 以下の環境変数が設定されている場合に AOAI を呼び出します。

```text
AZURE_OPENAI_ENDPOINT=https://<your-resource>.openai.azure.com/openai/v1/
AZURE_OPENAI_DEPLOYMENT_NAME=<your-deployment-name>
AOAI_MAX_TOKENS=400
```

- ローカル実行時は `az login` または Visual Studio Code の Azure サインイン状態を利用します。

- 未設定時はプレースホルダ回答を返します（`source: placeholder-rag`）。
- Azure Search の semantic 検索時は `source: azure-search-semantic` になります。
- Azure Search の semantic hybrid 検索時は `source: azure-search-semantic-hybrid` になります。
- AOAI呼び出し成功時は `source: rag+aoai` になります。

## テスト

`test_api.py` でスモークテストできます。

- 既定: App Service をテスト
```powershell
c:/vscodepy/apps-rag-simple/.venv/Scripts/python.exe test_api.py
```

- ローカルをテスト
```powershell
c:/vscodepy/apps-rag-simple/.venv/Scripts/python.exe test_api.py --base-url http://127.0.0.1:8000
```

## Azure App Service
- App Service（Linux/Python）にデプロイ可能なように `Procfile` を同梱しています。
- 本番URL: `https://apps-ketana-ext-rag-simple.azurewebsites.net`

## App Service へのデプロイ手順

以下は既存の App Service（`apps-ketana-ext-rag-simple`）へデプロイする手順です。

### 1) Azure ログイン
```powershell
az login
az account show
```

### 2) デプロイ先変数
```powershell
$app='apps-ketana-ext-rag-simple'
$rg='rg-ketana-ext-eastus2'
```

### 3) 起動コマンド設定
```powershell
az webapp config set -g $rg -n $app --startup-file 'gunicorn -k uvicorn.workers.UvicornWorker app.main:app --bind=0.0.0.0:$PORT'
```

### 4) App Settings 設定
```powershell
az webapp config appsettings set -g $rg -n $app --settings LOG_LEVEL=INFO AZURE_OPENAI_ENDPOINT='https://<your-resource>.openai.azure.com/openai/v1/' AZURE_OPENAI_DEPLOYMENT_NAME='<your-deployment-name>' AOAI_MAX_TOKENS=400 AZURE_OPENAI_EMBEDDING_MODEL='text-embedding-3-large' AZURE_SEARCH_ENDPOINT='https://<your-search-service>.search.windows.net' AZURE_SEARCH_INDEX_NAME='<your-index-name>' AZURE_SEARCH_API_KEY='<your-search-api-key>' AZURE_SEARCH_VECTOR_FIELD='contentVector' AZURE_SEARCH_SEMANTIC_CONFIG='<your-semantic-config-name>'
```

### 5) アプリ本体のみをZIP化してデプロイ
`test_api.py` などの補助ファイルは含めず、実行に必要なファイルのみデプロイします。

含める対象（今回成功した構成）:

- `app/`（API実装）
- `requirements.txt`（依存関係）
- `Procfile`（起動コマンド）

含めない対象（デプロイ不要）:

- `test_api.py`（テスト用）
- `docs/`（ドキュメント）
- `.venv/`（ローカル仮想環境）
- `.git/`, `.gitignore`（SCM管理情報）
- `.env`（ローカル設定ファイル）

```powershell
$zip='deploy-app-only.zip'
if (Test-Path $zip) { Remove-Item $zip -Force }
Compress-Archive -Path @('app','requirements.txt','Procfile') -DestinationPath $zip -CompressionLevel Optimal -Force
az webapp deploy -g $rg -n $app --src-path $zip --type zip --restart true
```

### 6) デプロイ後確認
```powershell
Invoke-RestMethod -Method Get -Uri https://apps-ketana-ext-rag-simple.azurewebsites.net/health

$body = @{ query = 'RAGとは何か' } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri https://apps-ketana-ext-rag-simple.azurewebsites.net/api/search -ContentType 'application/json' -Body $body
```
