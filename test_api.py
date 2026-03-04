import argparse
import json
import sys
import urllib.error
import urllib.request


def http_get_json(url: str, timeout: float) -> tuple[int, dict]:
    req = urllib.request.Request(url=url, method="GET")
    with urllib.request.urlopen(req, timeout=timeout) as res:
        body = res.read().decode("utf-8")
        return res.getcode(), json.loads(body)


def http_post_json(url: str, payload: dict, timeout: float) -> tuple[int, dict]:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url=url,
        data=data,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as res:
        body = res.read().decode("utf-8")
        return res.getcode(), json.loads(body)


def main() -> int:
    parser = argparse.ArgumentParser(description="API smoke test for apps-rag-simple")
    # local default (kept for reference): http://127.0.0.1:8000
    parser.add_argument(
        "--base-url",
        default="https://apps-ketana-ext-rag-simple.azurewebsites.net",
    )
    parser.add_argument("--query", default="高松コンストラクショングループの2025年3月期の受注高の計画は前期比何倍か、小数第三位を四捨五入し答えてください。")
    parser.add_argument("--timeout", type=float, default=90.0)
    args = parser.parse_args()

    base_url = args.base_url.rstrip("/")
    health_url = f"{base_url}/health"
    search_url = f"{base_url}/api/search"

    try:
        # health_status, health_body = http_get_json(health_url, args.timeout)
        # if health_status != 200 or health_body.get("status") != "ok":
        #     print("[FAIL] /health", health_status, health_body)
        #     return 1
        # print("[PASS] /health", health_body)

        search_status, search_body = http_post_json(
            search_url,
            {"query": args.query},
            args.timeout,
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

        print("[PASS] /api/search")
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
