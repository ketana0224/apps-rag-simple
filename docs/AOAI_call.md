# AOAI Call Sample Code (Secure)

ハードコードされた endpoint / api key は使用せず、環境変数と Microsoft Entra ID 認証を使う。

## Required environment variables

```text
AZURE_OPENAI_ENDPOINT=https://<your-resource>.openai.azure.com/openai/v1/
AZURE_OPENAI_DEPLOYMENT_NAME=<your-deployment-name>
```

## Python sample (Entra ID)

```python
import os

from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from openai import OpenAI

endpoint = os.getenv("AZURE_OPENAI_ENDPOINT", "").rstrip("/")
deployment_name = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "")

if not endpoint or not deployment_name:
    raise ValueError("AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_DEPLOYMENT_NAME are required")

if endpoint.endswith("/openai/v1"):
    base_url = f"{endpoint}/"
else:
    base_url = f"{endpoint}/openai/v1/"

token_provider = get_bearer_token_provider(
    DefaultAzureCredential(),
    "https://cognitiveservices.azure.com/.default",
)

client = OpenAI(
    base_url=base_url,
    api_key=token_provider,
)

response = client.responses.create(
    model=deployment_name,
    input="What is the capital of France?",
)

print(response.output_text)
```

## Notes

- ローカルでは `az login` 済みであること。
- 秘密情報（APIキー等）をソースコードやドキュメントに直書きしない。