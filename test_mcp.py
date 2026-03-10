import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request

from dotenv import load_dotenv


def _read_sse_first_event(response, timeout: float) -> str:
    event_lines: list[str] = []
    deadline = time.time() + min(timeout, 15.0)

    while time.time() < deadline:
        raw = response.readline()
        if not raw:
            break

        line = raw.decode("utf-8", errors="ignore").rstrip("\r\n")
        if line.startswith("data:"):
            event_lines.append(line[5:].strip())
            continue

        if line == "" and event_lines:
            break

    return "\n".join(event_lines).strip()


def post_jsonrpc(url: str, payload: dict, timeout: float, headers: dict | None = None) -> tuple[int, dict, str]:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url=url,
        data=data,
        method="POST",
        headers={"Content-Type": "application/json", **(headers or {})},
    )
    with urllib.request.urlopen(req, timeout=timeout) as res:
        response_headers = dict(res.headers)
        content_type = (res.headers.get("Content-Type") or "").lower()

        if "text/event-stream" in content_type:
            body = _read_sse_first_event(res, timeout)
            return res.getcode(), response_headers, body

        body = res.read().decode("utf-8")
        return res.getcode(), response_headers, body


def _required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ValueError(f"{name} is required")
    return value


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


def main() -> int:
    load_dotenv()

    parser = argparse.ArgumentParser(description="MCP smoke test for APIM-converted MCP endpoint")
    parser.add_argument(
        "--mcp-url",
        default=os.getenv(
            "MCP_SERVER_URL",
            "https://aigw-ketana-ext-japaneast.azure-api.net/simpe-rag/mcp",
        ),
    )
    parser.add_argument("--timeout", type=float, default=90.0)
    parser.add_argument(
        "--subscription-key",
        default=os.getenv("APIM_SUBSCRIPTION_KEY", ""),
        help="APIM subscription key (or set APIM_SUBSCRIPTION_KEY env var)",
    )
    parser.add_argument(
        "--auto-fetch-key",
        action="store_true",
        help="Auto-fetch APIM subscription key from Azure when --subscription-key is not set",
    )
    parser.add_argument(
        "--skip-tools-list",
        action="store_true",
        help="Run only initialize request",
    )
    parser.add_argument(
        "--call-search",
        action="store_true",
        help="Run tools/call for the search tool after tools/list",
    )
    parser.add_argument(
        "--tool-query",
        default="RAGとは何か",
        help="Query string to pass to search tool when --call-search is enabled",
    )
    args = parser.parse_args()

    subscription_key = (args.subscription_key or "").strip()
    if not subscription_key and args.auto_fetch_key:
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

    if not subscription_key:
        print("[INFO] APIM subscription key is not set; calling MCP endpoint without key")

    base_headers = {
        "Accept": "application/json, text/event-stream",
        "MCP-Protocol-Version": "2024-11-05",
    }
    if subscription_key:
        base_headers["Ocp-Apim-Subscription-Key"] = subscription_key

    initialize_payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "apim-mcp-smoke", "version": "1.0.0"},
        },
    }

    try:
        status, res_headers, init_body_text = post_jsonrpc(
            args.mcp_url,
            initialize_payload,
            args.timeout,
            headers=base_headers,
        )
        init_body = None
        if init_body_text:
            try:
                init_body = json.loads(init_body_text)
            except Exception:
                init_body = None

        if status != 200:
            print("[FAIL] initialize status", status, init_body_text)
            return 1
        if isinstance(init_body, dict) and "openapi" in init_body:
            print("[FAIL] endpoint returned OpenAPI document, not MCP JSON-RPC")
            print("[HINT] Verify APIM MCP conversion path and URL suffix")
            print(json.dumps(init_body, ensure_ascii=False, indent=2))
            return 1
        if init_body is not None and (init_body.get("jsonrpc") != "2.0" or ("result" not in init_body and "error" not in init_body)):
            print("[FAIL] initialize invalid response", init_body)
            return 1

        if init_body is None and not init_body_text:
            print("[INFO] initialize returned stream without immediate data event")
        else:
            print("[INFO] initialize payload:", init_body if init_body is not None else init_body_text)

        session_id = (
            res_headers.get("mcp-session-id")
            or res_headers.get("Mcp-Session-Id")
            or res_headers.get("MCP-Session-Id")
            or ""
        )
        print("[PASS] initialize")

        if args.skip_tools_list:
            return 0

        tools_headers = dict(base_headers)
        if session_id:
            tools_headers["mcp-session-id"] = session_id

        tools_list_payload = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {},
        }
        status2, _, tools_body_text = post_jsonrpc(
            args.mcp_url,
            tools_list_payload,
            args.timeout,
            headers=tools_headers,
        )

        tools_body = None
        if tools_body_text:
            try:
                tools_body = json.loads(tools_body_text)
            except Exception:
                tools_body = None

        if status2 != 200:
            print("[FAIL] tools/list status", status2, tools_body_text)
            return 1
        if tools_body is not None and (tools_body.get("jsonrpc") != "2.0" or ("result" not in tools_body and "error" not in tools_body)):
            print("[FAIL] tools/list invalid response", tools_body)
            return 1

        if tools_body is None and not tools_body_text:
            print("[PASS] tools/list stream opened (no immediate event payload)")
            return 0

        tools = []
        if isinstance(tools_body, dict):
            tools = tools_body.get("result", {}).get("tools", [])

        print(f"[PASS] tools/list (count={len(tools)})")
        if tools_body is not None:
            print(json.dumps(tools_body, ensure_ascii=False, indent=2))
        else:
            print(tools_body_text)

        if not args.call_search:
            return 0

        call_payload_candidates = [
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "search",
                    "arguments": {
                        "SearchRequest": {
                            "query": args.tool_query,
                        }
                    },
                },
            },
            {
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "search",
                    "arguments": {
                        "query": args.tool_query,
                    },
                },
            },
        ]

        last_error = ""
        for payload in call_payload_candidates:
            status3, _, call_body_text = post_jsonrpc(
                args.mcp_url,
                payload,
                args.timeout,
                headers=tools_headers,
            )

            call_body = None
            if call_body_text:
                try:
                    call_body = json.loads(call_body_text)
                except Exception:
                    call_body = None

            if status3 != 200:
                last_error = f"status={status3} body={call_body_text}"
                continue

            if isinstance(call_body, dict) and call_body.get("jsonrpc") == "2.0" and ("result" in call_body or "error" in call_body):
                if "error" in call_body:
                    last_error = json.dumps(call_body, ensure_ascii=False)
                    continue

                print("[PASS] tools/call (search)")
                print(json.dumps(call_body, ensure_ascii=False, indent=2))
                return 0

            if call_body_text:
                print("[PASS] tools/call (search)")
                print(call_body_text)
                return 0

            last_error = "empty tools/call response"

        print(f"[FAIL] tools/call failed: {last_error}")
        return 1

    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="ignore")
        try:
            detail_json = json.loads(detail)
            if isinstance(detail_json, dict) and "openapi" in detail_json:
                print("[FAIL] endpoint returned OpenAPI document, not MCP JSON-RPC")
                print("[HINT] Verify APIM MCP conversion path and URL suffix")
                print(json.dumps(detail_json, ensure_ascii=False, indent=2))
                return 1
        except Exception:
            pass
        print(f"[FAIL] HTTPError {e.code}: {detail}")
        return 1
    except Exception as e:
        print(f"[FAIL] Exception: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
