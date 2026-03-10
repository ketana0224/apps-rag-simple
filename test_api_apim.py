import argparse
import json
import os
import shutil
import subprocess
import sys
import urllib.error
import urllib.request

from dotenv import load_dotenv


def http_get_json(url: str, timeout: float, headers: dict | None = None) -> tuple[int, dict]:
    req = urllib.request.Request(url=url, method="GET", headers=headers or {})
    with urllib.request.urlopen(req, timeout=timeout) as res:
        body = res.read().decode("utf-8")
        return res.getcode(), json.loads(body)


def http_post_json(
    url: str,
    payload: dict,
    timeout: float,
    headers: dict | None = None,
) -> tuple[int, dict]:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url=url,
        data=data,
        method="POST",
        headers={"Content-Type": "application/json", **(headers or {})},
    )
    with urllib.request.urlopen(req, timeout=timeout) as res:
        body = res.read().decode("utf-8")
        return res.getcode(), json.loads(body)


def _required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ValueError(f"{name} is required")
    return value


def fetch_apim_subscription_key_from_az(timeout: float = 30.0) -> str:
    subscription_id = _required_env("APIM_AZURE_SUBSCRIPTION_ID")
    resource_group = _required_env("APIM_RESOURCE_GROUP")
    service_name = _required_env("APIM_SERVICE_NAME")
    apim_subscription_name = os.getenv("APIM_SUBSCRIPTION_NAME", "master").strip() or "master"

    url = (
        f"https://management.azure.com/subscriptions/{subscription_id}"
        f"/resourceGroups/{resource_group}"
        f"/providers/Microsoft.ApiManagement/service/{service_name}"
        f"/subscriptions/{apim_subscription_name}/listSecrets"
        "?api-version=2023-05-01-preview"
    )

    az_cli = resolve_az_cli_path()
    cmd = [
        az_cli,
        "rest",
        "--method",
        "post",
        "--url",
        url,
        "--only-show-errors",
        "-o",
        "json",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
    if result.returncode != 0:
        stderr = result.stderr.strip() or result.stdout.strip()
        raise RuntimeError(f"az rest failed: {stderr}")

    payload = json.loads(result.stdout)
    key = (payload.get("primaryKey") or payload.get("secondaryKey") or "").strip()
    if not key:
        raise RuntimeError("No APIM subscription key was returned by Azure")
    return key


def resolve_az_cli_path() -> str:
    env_path = os.getenv("AZ_CLI_PATH", "").strip()
    if env_path and os.path.exists(env_path):
        return env_path

    which_path = shutil.which("az")
    if which_path:
        return which_path

    windows_candidates = [
        r"C:\Program Files\Microsoft SDKs\Azure\CLI2\wbin\az.cmd",
        r"C:\Program Files (x86)\Microsoft SDKs\Azure\CLI2\wbin\az.cmd",
    ]
    for candidate in windows_candidates:
        if os.path.exists(candidate):
            return candidate

    raise RuntimeError("Azure CLI not found. Install Azure CLI or set AZ_CLI_PATH")


def main() -> int:
    load_dotenv()

    parser = argparse.ArgumentParser(description="API smoke test for APIM endpoint")
    parser.add_argument(
        "--base-url",
        default=os.getenv("APIM_BASE_URL", "https://aigw-ketana-ext-japaneast.azure-api.net/rag-simple"),
    )
    parser.add_argument(
        "--query",
        default="高松コンストラクショングループの2025年3月期の受注高の計画は前期比何倍か、小数第三位を四捨五入し答えてください。",
    )
    parser.add_argument("--timeout", type=float, default=90.0)
    parser.add_argument(
        "--subscription-key",
        default=os.getenv("APIM_SUBSCRIPTION_KEY", ""),
        help="APIM subscription key (or set APIM_SUBSCRIPTION_KEY env var)",
    )
    args = parser.parse_args()

    subscription_key = (args.subscription_key or "").strip()
    if not subscription_key:
        try:
            subscription_key = fetch_apim_subscription_key_from_az()
            print("[INFO] APIM subscription key was fetched from Azure")
        except Exception as e:
            print(f"[FAIL] APIM subscription key is required and auto-fetch failed: {e}")
            print(
                "[HINT] Set APIM_SUBSCRIPTION_KEY or configure "
                "APIM_AZURE_SUBSCRIPTION_ID/APIM_RESOURCE_GROUP/APIM_SERVICE_NAME/APIM_SUBSCRIPTION_NAME"
            )
            return 1

    base_url = args.base_url.rstrip("/")
    health_url = f"{base_url}/health"
    search_url = f"{base_url}/api/search"
    headers = {"Ocp-Apim-Subscription-Key": subscription_key}

    try:
        # health_status, health_body = http_get_json(health_url, args.timeout, headers=headers)
        # if health_status != 200 or health_body.get("status") != "ok":
        #     print("[FAIL] /health", health_status, health_body)
        #     return 1
        # print("[PASS] /health", health_body)

        search_status, search_body = http_post_json(
            search_url,
            {"query": args.query},
            args.timeout,
            headers=headers,
        )
        required_keys = {"query", "results", "answer", "source"}
        if search_status != 200:
            print("[FAIL] /api/search status", search_status, search_body)
            return 1
        if not required_keys.issubset(search_body.keys()):
            print("[FAIL] /api/search missing keys", search_body)
            return 1
        if search_body.get("source") not in {
            "placeholder-rag",
            "azure-search-semantic",
            "azure-search-semantic-hybrid",
            "rag+aoai",
        }:
            print("[FAIL] /api/search source", search_body.get("source"))
            return 1

        print("[PASS] /api/search (via APIM)")
        print(json.dumps(search_body, ensure_ascii=False, indent=2))
        return 0

    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="ignore")
        print(f"[FAIL] HTTPError {e.code}: {detail}")
        return 1
    except Exception as e:
        print(f"[FAIL] Exception: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
