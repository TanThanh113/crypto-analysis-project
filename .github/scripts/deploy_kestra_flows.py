from __future__ import annotations

import base64
import os
import pathlib
import sys
import urllib.error
import urllib.parse
import urllib.request

import yaml


TRUE_VALUES = {"1", "true", "yes", "y", "on"}


def env_bool(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in TRUE_VALUES


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


def is_ml_flow(path: pathlib.Path, flow_dir: pathlib.Path) -> bool:
    try:
        relative = path.relative_to(flow_dir)
    except ValueError:
        return False

    return bool(relative.parts and relative.parts[0] == "ml")


def deploy_files(
    *,
    files: list[pathlib.Path],
    kestra_server: str,
    tenant: str,
    headers: dict[str, str],
) -> int:
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

    return failed


def main() -> int:
    kestra_server = os.environ["KESTRA_SERVER"].rstrip("/")
    tenant = os.environ.get("KESTRA_TENANT", "main")
    flow_dir = pathlib.Path(os.environ["KESTRA_FLOW_DIR"])
    enable_ml_deploy = env_bool("ENABLE_ML_KESTRA_DEPLOY", default=False)

    files = sorted(flow_dir.rglob("*.yml")) + sorted(flow_dir.rglob("*.yaml"))

    if not files:
        print(f"No flow files found in {flow_dir}")
        print("No deployable Kestra flows; skipping Kestra server port-forward")
        return 0

    ml_files = [path for path in files if is_ml_flow(path, flow_dir)]
    non_ml_files = [path for path in files if not is_ml_flow(path, flow_dir)]
    ml_deployable_count = len(ml_files) if enable_ml_deploy else 0
    total_deployable_count = len(non_ml_files) + ml_deployable_count

    print(f"Detected non-ML Kestra flows to deploy: {len(non_ml_files)}")
    print(f"Detected ML Kestra flows: {len(ml_files)}")

    if not enable_ml_deploy:
        print("ENABLE_ML_KESTRA_DEPLOY=false; ML flows will be skipped")

    print(f"ML skipped count: {len(ml_files) - ml_deployable_count}")
    print(f"ML deployable count: {ml_deployable_count}")
    print(f"Total deployable count: {total_deployable_count}")

    if total_deployable_count == 0:
        print("No deployable Kestra flows; skipping Kestra server port-forward")
        return 0

    username = os.environ["KESTRA_USERNAME"]
    password = os.environ["KESTRA_PASSWORD"]

    token = base64.b64encode(
        f"{username}:{password}".encode("utf-8")
    ).decode("utf-8")

    headers = {
        "Authorization": f"Basic {token}",
        "Content-Type": "application/x-yaml",
    }

    print("Deploying batch/dbt/non-ML Kestra flows")
    failed = 0
    if non_ml_files:
        failed = deploy_files(
            files=non_ml_files,
            kestra_server=kestra_server,
            tenant=tenant,
            headers=headers,
        )

    deployed_count = len(non_ml_files)

    if enable_ml_deploy:
        print("Deploying ML Kestra flows because ENABLE_ML_KESTRA_DEPLOY=true")
        failed += deploy_files(
            files=ml_files,
            kestra_server=kestra_server,
            tenant=tenant,
            headers=headers,
        )
        deployed_count += len(ml_files)
    else:
        print("Skipping ML Kestra flows because ENABLE_ML_KESTRA_DEPLOY is not true")
        print(f"Skipped ML flow file count: {len(ml_files)}")

    if failed:
        print(f"Deployment failed: {failed} flow(s) failed.")
        return 1

    print(f"Deployment completed successfully: {deployed_count} flow file(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
