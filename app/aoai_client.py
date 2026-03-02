import os
from typing import Any

from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from openai import APIStatusError, OpenAI


def _is_placeholder(value: str) -> bool:
    return "<" in value and ">" in value


def generate_answer_with_aoai(
    query: str,
    results: list[dict[str, Any]],
    fallback_answer: str,
) -> tuple[str, bool]:
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT", "").rstrip("/")
    deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "")

    if (
        not endpoint
        or not deployment
        or _is_placeholder(endpoint)
        or _is_placeholder(deployment)
    ):
        return fallback_answer, False

    if endpoint.endswith("/openai/v1"):
        base_url = f"{endpoint}/"
    else:
        base_url = f"{endpoint}/openai/v1/"

    context_lines = []
    for item in results:
        title = str(item.get("title", ""))
        snippet = str(item.get("snippet", ""))
        context_lines.append(f"- {title}: {snippet}")

    context_text = "\n".join(context_lines) if context_lines else "- 参照コンテキストなし"

    prompt = (
        "あなたは検索結果に基づいて回答するアシスタントです。"
        "検索結果にない情報は推測せず、必要なら不明と述べてください。\n\n"
        f"質問: {query}\n\n"
        f"検索結果:\n{context_text}\n\n"
        "上記の検索結果だけを根拠に、日本語で簡潔に回答してください。"
    )

    token_provider = get_bearer_token_provider(
        DefaultAzureCredential(),
        "https://cognitiveservices.azure.com/.default",
    )

    client = OpenAI(base_url=base_url, api_key=token_provider, timeout=20.0)

    try:
        max_tokens = int(os.getenv("AOAI_MAX_TOKENS", "400"))
        if hasattr(client, "responses"):
            try:
                response = client.responses.create(
                    model=deployment,
                    input=prompt,
                )
            except APIStatusError as e:
                if e.status_code == 400:
                    response = client.responses.create(
                        model=deployment,
                        input=prompt,
                    )
                else:
                    raise
            answer = (getattr(response, "output_text", "") or "").strip()
        else:
            completion = client.chat.completions.create(
                model=deployment,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=max_tokens,
            )
            answer = (completion.choices[0].message.content or "").strip()
    except Exception:
        return fallback_answer, False

    if not answer:
        return fallback_answer, False

    return answer, True
