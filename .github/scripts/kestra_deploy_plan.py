from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path


TRUE_VALUES = {"1", "true", "yes", "y", "on"}


@dataclass(frozen=True)
class DeployPlan:
    has_changed_kestra_flow_files: bool
    has_non_ml_flows_to_deploy: bool
    has_ml_flows_to_deploy: bool
    should_deploy_ml_flows: bool
    has_any_flows_to_deploy: bool
    changed_kestra_flow_count: int
    non_ml_flow_count: int
    ml_flow_count: int
    ml_skipped_count: int
    total_deployable_count: int


def bool_text(value: bool) -> str:
    return "true" if value else "false"


def is_true(value: str | None) -> bool:
    return bool(value and value.strip().lower() in TRUE_VALUES)


def is_flow_file(path: str) -> bool:
    return path.endswith((".yml", ".yaml")) and path.startswith("kestra/flows-gke/")


def is_ml_flow(path: str) -> bool:
    return path.startswith("kestra/flows-gke/ml/")


def read_changed_files(path: Path) -> list[str]:
    if not path.exists():
        return []
    return [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def scan_flow_files(flow_root: Path) -> list[str]:
    files = sorted(flow_root.rglob("*.yml")) + sorted(flow_root.rglob("*.yaml"))
    return [str(path.as_posix()) for path in files]


def normalize_scanned_path(path: str) -> str:
    marker = "kestra/flows-gke/"
    if path.startswith(marker):
        return path
    if marker in path:
        return marker + path.split(marker, 1)[1]
    return path


def build_plan(
    *,
    event_name: str,
    enable_ml_kestra_deploy: str,
    changed_files: list[str],
    flow_root: Path,
) -> DeployPlan:
    if event_name == "pull_request":
        candidate_files = changed_files
    else:
        candidate_files = [normalize_scanned_path(path) for path in scan_flow_files(flow_root)]

    flow_files = [path for path in candidate_files if is_flow_file(path)]
    ml_flow_files = [path for path in flow_files if is_ml_flow(path)]
    non_ml_flow_files = [path for path in flow_files if not is_ml_flow(path)]

    enable_ml = is_true(enable_ml_kestra_deploy)
    should_deploy_ml = bool(ml_flow_files and enable_ml)
    ml_deployable_count = len(ml_flow_files) if should_deploy_ml else 0
    total_deployable_count = len(non_ml_flow_files) + ml_deployable_count

    return DeployPlan(
        has_changed_kestra_flow_files=bool(flow_files),
        has_non_ml_flows_to_deploy=bool(non_ml_flow_files),
        has_ml_flows_to_deploy=bool(ml_flow_files),
        should_deploy_ml_flows=should_deploy_ml,
        has_any_flows_to_deploy=total_deployable_count > 0,
        changed_kestra_flow_count=len(flow_files),
        non_ml_flow_count=len(non_ml_flow_files),
        ml_flow_count=len(ml_flow_files),
        ml_skipped_count=len(ml_flow_files) - ml_deployable_count,
        total_deployable_count=total_deployable_count,
    )


def write_github_output(path: str | None, plan: DeployPlan) -> None:
    if not path:
        return

    output_path = Path(path)
    with output_path.open("a", encoding="utf-8") as handle:
        for name in [
            "has_changed_kestra_flow_files",
            "has_non_ml_flows_to_deploy",
            "has_ml_flows_to_deploy",
            "should_deploy_ml_flows",
            "has_any_flows_to_deploy",
        ]:
            handle.write(f"{name}={bool_text(getattr(plan, name))}\n")

        for name in [
            "changed_kestra_flow_count",
            "non_ml_flow_count",
            "ml_flow_count",
            "ml_skipped_count",
            "total_deployable_count",
        ]:
            handle.write(f"{name}={getattr(plan, name)}\n")


def print_plan(plan: DeployPlan, enable_ml_kestra_deploy: str) -> None:
    print(f"has_changed_kestra_flow_files={bool_text(plan.has_changed_kestra_flow_files)}")
    print(f"has_non_ml_flows_to_deploy={bool_text(plan.has_non_ml_flows_to_deploy)}")
    print(f"has_ml_flows_to_deploy={bool_text(plan.has_ml_flows_to_deploy)}")
    print(f"should_deploy_ml_flows={bool_text(plan.should_deploy_ml_flows)}")
    print(f"has_any_flows_to_deploy={bool_text(plan.has_any_flows_to_deploy)}")
    print(f"Detected non-ML Kestra flows to deploy: {plan.non_ml_flow_count}")
    print(f"Detected ML Kestra flows: {plan.ml_flow_count}")
    if not is_true(enable_ml_kestra_deploy):
        print("ENABLE_ML_KESTRA_DEPLOY=false; ML flows will be skipped")
    print(f"ML skipped count: {plan.ml_skipped_count}")
    print(f"ML deployable count: {plan.ml_flow_count - plan.ml_skipped_count}")
    print(f"Total deployable count: {plan.total_deployable_count}")
    if not plan.has_any_flows_to_deploy:
        print("No deployable Kestra flows; skipping Kestra port-forward/deploy.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compute Kestra flow deploy plan.")
    parser.add_argument("--event-name", required=True)
    parser.add_argument("--enable-ml-kestra-deploy", default="false")
    parser.add_argument("--changed-files", type=Path, required=True)
    parser.add_argument("--flow-root", type=Path, default=Path("kestra/flows-gke"))
    parser.add_argument("--github-output")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    plan = build_plan(
        event_name=args.event_name,
        enable_ml_kestra_deploy=args.enable_ml_kestra_deploy,
        changed_files=read_changed_files(args.changed_files),
        flow_root=args.flow_root,
    )
    print_plan(plan, args.enable_ml_kestra_deploy)
    write_github_output(args.github_output, plan)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
