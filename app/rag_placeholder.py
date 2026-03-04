import logging
import os
from typing import Any

from azure.core.credentials import AzureKeyCredential
from azure.core.exceptions import HttpResponseError
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from azure.search.documents import SearchClient
from azure.search.documents.models import QueryType, VectorizedQuery
from openai import OpenAI


logger = logging.getLogger(__name__)


def _is_placeholder(value: str) -> bool:
    return "<" in value and ">" in value


def _get_search_client(endpoint: str, index_name: str) -> SearchClient:
    api_key = os.getenv("AZURE_SEARCH_API_KEY", "").strip()

    if api_key:
        return SearchClient(
            endpoint=endpoint,
            index_name=index_name,
            credential=AzureKeyCredential(api_key),
        )

    return SearchClient(
        endpoint=endpoint,
        index_name=index_name,
        credential=DefaultAzureCredential(),
    )


def _embed_query_with_aoai(query: str) -> list[float]:
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT", "").rstrip("/")
    if not endpoint or _is_placeholder(endpoint):
        raise RuntimeError("AZURE_OPENAI_ENDPOINT is not configured")

    if endpoint.endswith("/openai/v1"):
        base_url = f"{endpoint}/"
    else:
        base_url = f"{endpoint}/openai/v1/"

    embedding_model = os.getenv("AZURE_OPENAI_EMBEDDING_MODEL", "text-embedding-3-large")
    token_provider = get_bearer_token_provider(
        DefaultAzureCredential(),
        "https://cognitiveservices.azure.com/.default",
    )
    client = OpenAI(base_url=base_url, api_key=token_provider, timeout=20.0)

    response = client.embeddings.create(model=embedding_model, input=query)
    if not response.data:
        raise RuntimeError("embedding response is empty")
    return response.data[0].embedding


def _to_result_item(document: dict[str, Any]) -> dict[str, Any]:
    doc_id = (
        document.get("id")
        or document.get("chunk_id")
        or document.get("metadata_storage_path")
        or "unknown"
    )
    title = document.get("title") or document.get("file_name") or str(doc_id)
    snippet = (
        document.get("content")
        or document.get("chunk")
        or document.get("text")
        or ""
    )

    score = document.get("@search.score")
    reranker_score = document.get("@search.reranker_score")
    if reranker_score is not None:
        score = reranker_score

    return {
        "id": str(doc_id),
        "title": str(title),
        "snippet": str(snippet),
        "score": float(score) if score is not None else 0.0,
    }


def _search_semantic_hybrid(
    search_client: SearchClient,
    query_text: str,
    query_vector: list[float],
    vector_field: str,
    semantic_config: str,
):
    vector_query = VectorizedQuery(
        vector=query_vector,
        fields=vector_field,
        k_nearest_neighbors=5,
    )

    search_kwargs: dict[str, Any] = {
        "search_text": query_text,
        "vector_queries": [vector_query],
        "query_type": QueryType.SEMANTIC,
        "top": 5,
    }
    if semantic_config:
        search_kwargs["semantic_configuration_name"] = semantic_config

    return search_client.search(**search_kwargs), "azure-search-semantic-hybrid"


def _search_semantic_only(
    search_client: SearchClient,
    query_text: str,
    semantic_config: str,
):
    search_kwargs: dict[str, Any] = {
        "search_text": query_text,
        "query_type": QueryType.SEMANTIC,
        "top": 5,
    }
    if semantic_config:
        search_kwargs["semantic_configuration_name"] = semantic_config

    return search_client.search(**search_kwargs), "azure-search-semantic"


def search(query: str) -> dict[str, Any]:
    normalized_query = query.strip()

    endpoint = os.getenv("AZURE_SEARCH_ENDPOINT", "").rstrip("/")
    index_name = os.getenv("AZURE_SEARCH_INDEX_NAME", "")
    vector_field = os.getenv("AZURE_SEARCH_VECTOR_FIELD", "contentVector")
    semantic_config = os.getenv("AZURE_SEARCH_SEMANTIC_CONFIG", "")

    if (
        not endpoint
        or not index_name
        or _is_placeholder(endpoint)
        or _is_placeholder(index_name)
    ):
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

    try:
        search_client = _get_search_client(endpoint=endpoint, index_name=index_name)
        source = "azure-search-semantic-hybrid"
        try:
            query_vector = _embed_query_with_aoai(normalized_query)
            documents, source = _search_semantic_hybrid(
                search_client=search_client,
                query_text=normalized_query,
                query_vector=query_vector,
                vector_field=vector_field,
                semantic_config=semantic_config,
            )
        except Exception:
            logger.exception("embedding failed, fallback to semantic only")
            documents, source = _search_semantic_only(
                search_client=search_client,
                query_text=normalized_query,
                semantic_config=semantic_config,
            )

        results = [_to_result_item(doc) for doc in documents]

        fallback_answer = (
            results[0]["snippet"]
            if results
            else "検索結果が見つかりませんでした。"
        )

        return {
            "query": normalized_query,
            "results": results,
            "answer": fallback_answer,
            "source": source,
        }
    except HttpResponseError:
        logger.exception("azure search query failed")
    except Exception:
        logger.exception("rag search failed")

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
