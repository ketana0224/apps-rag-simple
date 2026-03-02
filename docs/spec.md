# AI駆動開発 仕様書（MVP）

## 1. 概要
- 本仕様は、RAG（Retrieval-Augmented Generation）向けの検索アプリを最小構成で実装するためのものとする。
- 初期版では、RAG検索はプレースホルダ実装とし、検索結果を根拠に Azure OpenAI（AOAI）で回答生成を試行する。
- デプロイ先は Azure App Service とする。

## 2. 目的
- APIクライアントから検索クエリを送信し、検索結果を取得できること。
- 将来的な本実装（ベクトル検索・再ランキング・回答生成）へ差し替え可能な設計にすること。
- Azure App Service 上で動作確認できること。

## 3. スコープ
### 3.1 対象
- 検索API（バックエンド）
- RAG検索プレースホルダ
- AOAI回答生成（Microsoft Entra ID認証）
- Azure App Service へのデプロイ設定

### 3.2 非対象（MVP外）
- 実際のベクトルDB接続
- 埋め込み生成・インデックス作成パイプライン
- 認証・認可（ログイン）
- 高度な監視・自動スケーリング最適化

## 4. 想定ユーザー
- 社内検証ユーザー（開発者・企画担当）

## 5. 機能要件
### 5.1 API入力
- APIクライアント（例: curl, Postman）から検索クエリを送信できる。
- リクエストはJSON形式で受け付ける。

### 5.2 検索API呼び出し
- エンドポイント: `POST /api/search`
- リクエスト（JSON）:
	- `query`: string（必須）
- レスポンス（JSON）:
	- `query`: string
	- `results`: array
	- `answer`: string
	- `source`: string（`placeholder-rag` または `rag+aoai`）

### 5.3 RAG検索（プレースホルダ）
- `query` を受け取り、固定または疑似的な検索結果を返す。
- 返却データは将来の本実装と互換性を持つ形式にする。
- 実装箇所を明確化し、後で本物のRAG処理へ差し替え可能にする。

### 5.4 AOAI回答生成
- RAG検索結果をコンテキストとして AOAI の Responses API を呼び出し、回答生成を試行する。
- 認証は Microsoft Entra ID（`DefaultAzureCredential`）を使用する。
- `AZURE_OPENAI_ENDPOINT` と `AZURE_OPENAI_DEPLOYMENT_NAME` が未設定、または呼び出し失敗時はプレースホルダ回答へフォールバックする。
- AOAI呼び出し成功時は `source` を `rag+aoai` とする。

### 5.5 エラーハンドリング
- `query` が空の場合は `400 Bad Request` を返す。
- サーバー内部エラー時は `500 Internal Server Error` を返す。

## 6. 非機能要件
- 応答時間（MVP目標）: 通常時 2秒以内
- ログ: APIリクエストとエラーを標準出力に記録
- 設定値は環境変数で管理（ハードコードしない）
- ローカル実行時の Entra 認証は `az login` 等で事前ログイン済みであること

## 7. API仕様（詳細）
### 7.1 `POST /api/search`
#### Request
```json
{
	"query": "RAGとは何か"
}
```

#### Response（200）
```json
{
	"query": "RAGとは何か",
	"results": [
		{
			"id": "doc-001",
			"title": "RAG入門（プレースホルダ）",
			"snippet": "これはプレースホルダの検索結果です。",
			"score": 0.99
		}
	],
	"answer": "提示された検索結果には「RAGとは何か」についての具体的な説明は含まれていません。そのため、RAGの内容は不明です。",
	"source": "rag+aoai"
}
```

#### Response（200, フォールバック時）
```json
{
	"query": "RAGとは何か",
	"results": [
		{
			"id": "doc-001",
			"title": "RAG入門（プレースホルダ）",
			"snippet": "これはプレースホルダの検索結果です。",
			"score": 0.99
		}
	],
	"answer": "これはプレースホルダ応答です。後で実際のRAG回答に置き換えます。",
	"source": "placeholder-rag"
}
```

## 8. システム構成（MVP）
- バックエンド: 検索API（`/api/search`）
- RAG層: プレースホルダ実装
- 生成層: Azure OpenAI Responses API（Entra認証）
- ホスティング: Azure App Service

## 9. デプロイ要件（Azure App Service）
- Azure App Service 上でWebアプリとして公開する。
- 実行時設定（環境変数）を App Service のアプリ設定に登録する。
- 起動コマンド/ポート設定は使用ランタイムに合わせて構成する。
- デプロイ後に `POST /api/search` の疎通確認を行う。
- デプロイ先アプリ名: `apps-ketana-ext-rag-simple`
- 必須環境変数: `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_DEPLOYMENT_NAME`

## 10. 受け入れ基準
- APIクライアントから検索クエリを送信し、APIレスポンスを取得できる。
- `POST /api/search` が仕様どおりのJSONを返す。
- RAG処理がプレースホルダ実装として分離されている。
- AOAI呼び出し成功時に `source=rag+aoai` を返す。
- AOAI未設定/失敗時に `source=placeholder-rag` でフォールバックする。
- Azure App Service 上でアプリにアクセスできる。

## 11. テスト
- スモークテストスクリプト: `test_api.py`
- 既定接続先は App Service URL（ローカルURLはコメントで保持）
- `GET /health` および `POST /api/search` を検証する。

## 12. 今後の拡張
- ベクトルDB連携（例: Azure AI Search など）
- 埋め込み生成とインデックス更新バッチ
- 回答生成の品質改善（再ランキング、プロンプト最適化）
- 認証・認可、監視、CI/CDの強化
