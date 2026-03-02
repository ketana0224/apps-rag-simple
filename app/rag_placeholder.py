from typing import Any


def search(query: str) -> dict[str, Any]:
    normalized_query = query.strip()
    return {
        "query": normalized_query,
        "results": [
            {
                "id": "doc-001",
                "title": "RAG入門（プレースホルダ）",
                "snippet": "これはプレースホルダの検索結果です。",
                "score": 0.99,
            }
        ],
        "answer": "これはプレースホルダ応答です。後で実際のRAG回答に置き換えます。",
        "source": "placeholder-rag",
    }
