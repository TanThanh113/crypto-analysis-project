from __future__ import annotations

import base64
import os
import pathlib
import sys
import urllib.error
import urllib.parse
import urllib.request

import yaml


def request(
    *,
    method: str,
    url: str,
    headers: dict[str, str],
    body: bytes | None = None,
) -> tuple[int, str]:
    req = urllib.request.Request(
        url=url,
        data=body,
        headers=headers,
        method=method,
    )

    try:
        with urllib.request.urlopen(req, timeout=60) as response:
            payload = response.read().decode("utf-8", errors="replace")
            return response.status, payload
    except urllib.error.HTTPError as exc:
        payload = exc.read().decode("utf-8", errors="replace")
        return exc.code, payload


def scan_invalid_boolean(obj) -> bool:
    if isinstance(obj, dict):
        if obj.get("type") == "BOOLEAN":
            return True
        return any(scan_invalid_boolean(value) for value in obj.values())

    if isinstance(obj, list):
        return any(scan_invalid_boolean(item) for item in obj)

    return False


def deploy_flow(
    *,
    path: pathlib.Path,
    kestra_server: str,
    tenant: str,
    headers: dict[str, str],
) -> bool:
    source = path.read_text(encoding="utf-8")
    flow = yaml.safe_load(source)

    if not isinstance(flow, dict):
        print(f"SKIP non-flow file: {path}")
        return True

    flow_id = flow.get("id")
    namespace = flow.get("namespace")

    if not flow_id or not namespace:
        print(f"ERROR {path}: missing id or namespace")
        return False

    if "labels" in flow and not isinstance(flow["labels"], dict):
        label_type = type(flow["labels"]).__name__
        print(f"ERROR {path}: labels must be object/map, got {label_type}")
        return False

    if scan_invalid_boolean(flow):
        print(f"ERROR {path}: contains invalid input type BOOLEAN. Use BOOL.")
        return False

    body = source.encode("utf-8")

    ns_encoded = urllib.parse.quote(str(namespace), safe="")
    id_encoded = urllib.parse.quote(str(flow_id), safe="")

    update_url = f"{kestra_server}/api/v1/{tenant}/flows/{ns_encoded}/{id_encoded}"
    create_url = f"{kestra_server}/api/v1/{tenant}/flows"

    status, payload = request(
        method="PUT",
        url=update_url,
        headers=headers,
        body=body,
    )

    if 200 <= status < 300:
        print(f"UPDATED {namespace}.{flow_id}")
        return True

    if status in {404, 405}:
        status, payload = request(
            method="POST",
            url=create_url,
            headers=headers,
            body=body,
        )

        if 200 <= status < 300:
            print(f"CREATED {namespace}.{flow_id}")
            return True

    print(f"FAILED {namespace}.{flow_id} from {path}")
    print(f"HTTP status: {status}")
    print(payload[:2000])
    return False


def main() -> int:
    kestra_server = os.environ["KESTRA_SERVER"].rstrip("/")
    tenant = os.environ.get("KESTRA_TENANT", "main")
    flow_dir = pathlib.Path(os.environ["KESTRA_FLOW_DIR"])

    username = os.environ["KESTRA_USERNAME"]
    password = os.environ["KESTRA_PASSWORD"]

    token = base64.b64encode(
        f"{username}:{password}".encode("utf-8")
    ).decode("utf-8")

    headers = {
        "Authorization": f"Basic {token}",
        "Content-Type": "application/x-yaml",
    }

    files = sorted(flow_dir.rglob("*.yml")) + sorted(flow_dir.rglob("*.yaml"))

    if not files:
        print(f"No flow files found in {flow_dir}")
        return 1

    failed = 0

    for path in files:
        ok = deploy_flow(
            path=path,
            kestra_server=kestra_server,
            tenant=tenant,
            headers=headers,
        )

        if not ok:
            failed += 1

    if failed:
        print(f"Deployment failed: {failed} flow(s) failed.")
        return 1

    print(f"Deployment completed successfully: {len(files)} flow file(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
