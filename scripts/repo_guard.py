import re
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]

WORKFLOWS_DIR = PROJECT_ROOT / ".github" / "workflows"
GKE_FLOWS_DIR = PROJECT_ROOT / "kestra" / "flows-gke"


class Violation:
    def __init__(self, file_path: Path, message: str, line_no: int | None = None, line: str | None = None):
        self.file_path = file_path
        self.message = message
        self.line_no = line_no
        self.line = line

    def render(self) -> str:
        rel = self.file_path.relative_to(PROJECT_ROOT)
        if self.line_no is None:
            return f"❌ {rel}: {self.message}"

        return f"❌ {rel}:{self.line_no}: {self.message}\n   ↳ {self.line.strip()}"


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def iter_files(root: Path, suffixes: tuple[str, ...]) -> list[Path]:
    if not root.exists():
        return []

    return [
        path
        for path in root.rglob("*")
        if path.is_file() and path.suffix in suffixes
    ]


def find_pattern(path: Path, pattern: str, message: str) -> list[Violation]:
    violations = []
    regex = re.compile(pattern)

    for line_no, line in enumerate(read_text(path).splitlines(), start=1):
        if regex.search(line):
            violations.append(Violation(path, message, line_no, line))

    return violations


def check_kestra_deploy_paths() -> list[Violation]:
    """
    Ensure GitHub Actions deploys only kestra/flows-gke, not legacy kestra/flows.
    """
    violations = []

    for path in iter_files(WORKFLOWS_DIR, (".yml", ".yaml")):
        if path.name == "quality-check.yml":
            continue

        content = read_text(path)

        legacy_patterns = [
            r"kestractl\s+flows\s+deploy\s+\.?/??kestra/flows(\s|$)",
            r"directory:\s*\.?/??kestra/flows\s*$",
        ]

        for pattern in legacy_patterns:
            for line_no, line in enumerate(content.splitlines(), start=1):
                if re.search(pattern, line):
                    violations.append(
                        Violation(
                            path,
                            "Legacy Kestra deploy path detected. Use ./kestra/flows-gke only.",
                            line_no,
                            line,
                        )
                    )

    return violations


def check_gke_flows_do_not_use_legacy_runtime() -> list[Violation]:
    """
    GKE flows must use Kubernetes PodCreate + Workload Identity.
    They must not use Docker runner, service account JSON keys, or local machine paths.
    """
    violations = []

    forbidden_patterns = {
        r"io\.kestra\.plugin\.scripts\.runner\.docker\.Docker": "GKE flow must not use Kestra Docker runner.",
        r"GOOGLE_APPLICATION_CREDENTIALS": "GKE flow must not use GOOGLE_APPLICATION_CREDENTIALS.",
        r"gcp-key\.json": "GKE flow must not use service-account JSON key file.",
        r"inputFiles\s*:": "GKE flow must not inject credentials through inputFiles.",
        r"secret\('GCP_CREDS'\)": "GKE flow must not use GCP_CREDS JSON secret.",
        r"networkMode\s*:": "GKE flow must not use local Docker networkMode.",
        r"pullPolicy:\s*NEVER": "GKE flow must not use local-only pullPolicy NEVER.",
        r"/home/thanh": "GKE flow must not reference local machine paths.",
        r"image:\s*['\"]?crypto-(batch|dbt|ml):latest": "GKE flow must use full Artifact Registry image path.",
    }

    for path in iter_files(GKE_FLOWS_DIR, (".yml", ".yaml")):
        for pattern, message in forbidden_patterns.items():
            violations.extend(find_pattern(path, pattern, message))

    return violations


def check_gke_flows_use_artifact_registry_images() -> list[Violation]:
    """
    Any container image in flows-gke should come from Artifact Registry, except public utility images if added later.
    """
    violations = []

    allowed_prefixes = (
        "asia-southeast1-docker.pkg.dev/project-lambda-crypto/crypto-docker/",
        "debian:",
        "busybox:",
    )

    image_pattern = re.compile(r"^\s*image:\s*([^\s#]+)\s*$")

    for path in iter_files(GKE_FLOWS_DIR, (".yml", ".yaml")):
        for line_no, line in enumerate(read_text(path).splitlines(), start=1):
            match = image_pattern.search(line)
            if not match:
                continue

            image = match.group(1).strip().strip('"').strip("'")
            if not image.startswith(allowed_prefixes):
                violations.append(
                    Violation(
                        path,
                        f"Unexpected image '{image}'. Use Artifact Registry images for production GKE flows.",
                        line_no,
                        line,
                    )
                )

    return violations


def check_workflows_checkout_version() -> list[Violation]:
    """
    Prefer checkout@v5 to avoid Node.js 20 deprecation warnings.
    """
    violations = []

    for path in iter_files(WORKFLOWS_DIR, (".yml", ".yaml")):
        violations.extend(
            find_pattern(
                path,
                r"uses:\s*actions/checkout@v4",
                "Use actions/checkout@v5.",
            )
        )

    return violations


def main() -> int:
    print("🔍 Running production repository guard...")

    checks = [
        ("Kestra deploy path guard", check_kestra_deploy_paths),
        ("GKE flow legacy runtime guard", check_gke_flows_do_not_use_legacy_runtime),
        ("GKE image source guard", check_gke_flows_use_artifact_registry_images),
        ("GitHub Actions version guard", check_workflows_checkout_version),
    ]

    all_violations: list[Violation] = []

    for check_name, check_fn in checks:
        print(f"\n▶ {check_name}")
        violations = check_fn()

        if not violations:
            print("✅ OK")
            continue

        for violation in violations:
            print(violation.render())

        all_violations.extend(violations)

    if all_violations:
        print(f"\n🛑 Repository guard failed: {len(all_violations)} violation(s) found.")
        return 1

    print("\n✅ All production repository guard checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
