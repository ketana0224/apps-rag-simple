import argparse
import csv
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path


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


def load_queries(csv_path: Path) -> list[tuple[str, str]]:
    queries: list[tuple[str, str]] = []
    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if "problem" not in (reader.fieldnames or []):
            raise ValueError("CSV must contain 'problem' column")

        for i, row in enumerate(reader):
            query = (row.get("problem") or "").strip()
            if not query:
                continue
            index = (row.get("index") or str(i)).strip()
            queries.append((index, query))

    return queries


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Loop /api/search with problems in test_query.csv"
    )
    parser.add_argument(
        "--base-url",
        default="https://apps-ketana-ext-rag-simple.azurewebsites.net",
    )
    parser.add_argument("--csv", default="test_query.csv")
    parser.add_argument("--timeout", type=float, default=90.0)
    parser.add_argument("--limit", type=int, default=0, help="0 means all rows")
    args = parser.parse_args()

    base_url = args.base_url.rstrip("/")
    search_url = f"{base_url}/api/search"
    csv_path = Path(args.csv)

    if not csv_path.exists():
        print(f"[FAIL] CSV not found: {csv_path}")
        return 1

    try:
        queries = load_queries(csv_path)
    except Exception as e:
        print(f"[FAIL] CSV load error: {e}")
        return 1

    if args.limit > 0:
        queries = queries[: args.limit]

    if not queries:
        print("[FAIL] no queries in CSV")
        return 1

    required_keys = {"query", "results", "answer", "source"}
    valid_sources = {
        "placeholder-rag",
        "azure-search-semantic",
        "azure-search-semantic-hybrid",
        "rag+aoai",
    }

    ok = 0
    ng = 0

    for index, query in queries:
        try:
            status, body = http_post_json(search_url, {"query": query}, args.timeout)
            if status != 200:
                print(f"[FAIL] idx={index} status={status}")
                ng += 1
                continue
            if not required_keys.issubset(body.keys()):
                print(f"[FAIL] idx={index} missing_keys")
                ng += 1
                continue
            if body.get("source") not in valid_sources:
                print(f"[FAIL] idx={index} invalid_source={body.get('source')}")
                ng += 1
                continue

            print(f"[PASS] idx={index} source={body.get('source')} query={query}")
            print(f'"answer": "{body.get("answer", "")}"')
            ok += 1
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", errors="ignore")
            print(f"[FAIL] idx={index} HTTPError {e.code}: {detail}")
            ng += 1
        except Exception as e:
            print(f"[FAIL] idx={index} Exception: {e}")
            ng += 1

    print(f"\nSummary: total={len(queries)} pass={ok} fail={ng}")
    return 0 if ng == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
