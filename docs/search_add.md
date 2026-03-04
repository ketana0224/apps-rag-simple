# Azure AI Search Call Sample Code (Secure)

rag_placeholder.pyにAzure AI Searchの検索処理を追加する

# AI Seaarch Config
endpoint=https://ketana-ext-search.search.windows.net
apikey=<set-in-env-or-appsettings>
indexname=fdua_index
ハードコードせずに環境変数を使うこと

# 検索方法
Semantic Hybrid Search

# 結果の数(k)
5

# 質問ベクター化方法
aoai_client.pyを参考に同じendpointを使う
model=text-embedding-3-large