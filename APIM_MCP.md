# APIM MCP サーバー再作成手順（`simpe-rag`）

この手順は `aigw-ketana-ext-japaneast` 上の MCP サーバー `simpe-rag` を
一度消して作り直すための実行ログ付き手順です。

## 前提

- サブスクリプション: `571e49d7-d4d6-4cb5-884f-2e14bfaa662c`
- リソースグループ: `rg-ketana-ext-japaneast`
- APIM サービス: `aigw-ketana-ext-japaneast`
- ソース API: `apps-rag-simple`
- 対象操作: `search_api_search_post`

## 1. 現在の API 一覧確認

```powershell
az rest --method get --url "https://management.azure.com/subscriptions/571e49d7-d4d6-4cb5-884f-2e14bfaa662c/resourceGroups/rg-ketana-ext-japaneast/providers/Microsoft.ApiManagement/service/aigw-ketana-ext-japaneast/apis?api-version=2024-10-01-preview" --query "value[].name" -o tsv
```

確認時点では `simpe-rag` は存在しない状態でした。

## 2. `apps-rag-simple` の Search operationId 取得

```powershell
az rest --method get --url "https://management.azure.com/subscriptions/571e49d7-d4d6-4cb5-884f-2e14bfaa662c/resourceGroups/rg-ketana-ext-japaneast/providers/Microsoft.ApiManagement/service/aigw-ketana-ext-japaneast/apis/apps-rag-simple/operations/search_api_search_post?api-version=2024-10-01-preview" --query id -o tsv
```

## 3. `simpe-rag` を MCP API として再作成

```powershell
$opId = az rest --method get --url "https://management.azure.com/subscriptions/571e49d7-d4d6-4cb5-884f-2e14bfaa662c/resourceGroups/rg-ketana-ext-japaneast/providers/Microsoft.ApiManagement/service/aigw-ketana-ext-japaneast/apis/apps-rag-simple/operations/search_api_search_post?api-version=2024-10-01-preview" --query id -o tsv

$payload = @{
  properties = @{
    displayName = 'simpe-rag'
    path = 'simpe-rag'
    protocols = @('https')
    type = 'mcp'
    subscriptionRequired = $false
    mcpTools = @(
      @{
        name = 'search'
        description = 'Search'
        operationId = $opId
      }
    )
  }
} | ConvertTo-Json -Depth 20

Set-Content -Path scripts/simpe-rag.create.json -Value $payload -Encoding UTF8

az rest --method put --url "https://management.azure.com/subscriptions/571e49d7-d4d6-4cb5-884f-2e14bfaa662c/resourceGroups/rg-ketana-ext-japaneast/providers/Microsoft.ApiManagement/service/aigw-ketana-ext-japaneast/apis/simpe-rag?api-version=2024-10-01-preview" --headers "Content-Type=application/json" --body "@scripts/simpe-rag.create.json" -o json
```

作成結果:

- `name: simpe-rag`
- `properties.type: mcp`
- `properties.path: simpe-rag`
- `properties.subscriptionRequired: false`
- `properties.mcpTools[0].operationId: .../apis/apps-rag-simple/operations/search_api_search_post`

## 4. 再作成後の疎通確認

```powershell
c:/vscodepy/apps-rag-simple/.venv/Scripts/python.exe test_mcp.py --skip-tools-list --mcp-url https://aigw-ketana-ext-japaneast.azure-api.net/simpe-rag/mcp
c:/vscodepy/apps-rag-simple/.venv/Scripts/python.exe test_mcp.py --mcp-url https://aigw-ketana-ext-japaneast.azure-api.net/simpe-rag/mcp
```

当初結果:

- どちらも `HTTP 400: Invalid JSON payload`

## 4.1 400 エラーの根本原因（確定）

APIM MCP エンドポイントは、JSON-RPC の `id` で `"init-1"` や `"tools-1"` のような値を受け付けず、
`1` / `2` などのシンプルな数値（または `"1"` 形式）を使う必要がありました。

### NG 例

```json
{"jsonrpc":"2.0","id":"init-1","method":"initialize",...}
```

### OK 例

```json
{"jsonrpc":"2.0","id":1,"method":"initialize",...}
```

## 4.2 修正後の検証結果

`test_mcp.py` の JSON-RPC `id` を `1` / `2` に変更後、以下で成功しました。

```powershell
c:/vscodepy/apps-rag-simple/.venv/Scripts/python.exe test_mcp.py --skip-tools-list --mcp-url https://aigw-ketana-ext-japaneast.azure-api.net/simpe-rag/mcp
c:/vscodepy/apps-rag-simple/.venv/Scripts/python.exe test_mcp.py --mcp-url https://aigw-ketana-ext-japaneast.azure-api.net/simpe-rag/mcp
```

成功内容:

- `[PASS] initialize`
- `[PASS] tools/list (count=1)`
- 取得ツール: `search`

## 4.3 tools/call（search）検証

`test_mcp.py` を拡張し、`tools/call` で `search` を呼び出せるようにしました。

```powershell
c:/vscodepy/apps-rag-simple/.venv/Scripts/python.exe test_mcp.py --mcp-url https://aigw-ketana-ext-japaneast.azure-api.net/simpe-rag/mcp --call-search --tool-query "RAGとは何か"
```

結果:

- `tools/call` 自体は成功
- キーなし実行では、ツール結果本文が `401`（バックエンド API 側のキー不足）

キー付き実行:

```powershell
c:/vscodepy/apps-rag-simple/.venv/Scripts/python.exe test_mcp.py --mcp-url https://aigw-ketana-ext-japaneast.azure-api.net/simpe-rag/mcp --call-search --tool-query "RAGとは何か" --auto-fetch-key
```

結果:

- `initialize` / `tools/list` / `tools/call(search)` すべて成功
- `tools/call` で実データ（検索結果と回答）を取得できることを確認

## 5. 補足（設定画面がグレーアウトする理由）

`simpe-rag` は APIM の `type=mcp` API です。管理 API 上でも `serviceUrl=null` で管理されるため、
Portal の `ベース URL` が編集不可（グレーアウト）なのは正常挙動です。

## 6. 次の切り分け

1. Portal の `simpe-rag > MCP > ツール` で `Search` のみ選択（`Health` は外す）
2. 保存後、再度 `test_mcp.py` を実行
3. まだ 400 の場合、APIM 側の MCP 実装が受けるペイロード形式を確認（Portal テストコンソール/公式サンプルに合わせる）

---

本ファイルは確定版として利用可能です。
