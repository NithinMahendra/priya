import json
import re
from dataclasses import dataclass
from typing import Any


@dataclass
class VulnerabilityRule:
    package: str
    safe_version: str
    severity: str
    message: str
    suggested_fix: str


class DependencyScanner:
    PY_RULES = [
        VulnerabilityRule(
            package="django",
            safe_version="4.2.16",
            severity="High",
            message="Outdated Django may include known security vulnerabilities.",
            suggested_fix="Upgrade Django to >=4.2.16 or current supported LTS release.",
        ),
        VulnerabilityRule(
            package="pyyaml",
            safe_version="6.0.1",
            severity="High",
            message="Older PyYAML versions can expose unsafe deserialization risks.",
            suggested_fix="Upgrade PyYAML and always prefer yaml.safe_load for untrusted inputs.",
        ),
        VulnerabilityRule(
            package="requests",
            safe_version="2.32.0",
            severity="Medium",
            message="Older requests versions may miss critical security patches.",
            suggested_fix="Upgrade requests to latest stable release.",
        ),
    ]
    NPM_RULES = [
        VulnerabilityRule(
            package="lodash",
            safe_version="4.17.21",
            severity="High",
            message="Older lodash versions have prototype pollution vulnerabilities.",
            suggested_fix="Upgrade lodash to >=4.17.21.",
        ),
        VulnerabilityRule(
            package="minimist",
            safe_version="1.2.8",
            severity="High",
            message="Older minimist versions are vulnerable to prototype pollution.",
            suggested_fix="Upgrade minimist to >=1.2.8.",
        ),
        VulnerabilityRule(
            package="axios",
            safe_version="1.6.8",
            severity="Medium",
            message="Outdated axios may include client-side request vulnerabilities.",
            suggested_fix="Upgrade axios to >=1.6.8.",
        ),
    ]

    def scan(self, manifest: str, manifest_type: str | None = None) -> list[dict[str, Any]]:
        kind = self._normalize_manifest_type(manifest_type, manifest)
        if kind == "requirements":
            return self._scan_requirements(manifest)
        if kind == "package_json":
            return self._scan_package_json(manifest)
        return []

    def _normalize_manifest_type(self, manifest_type: str | None, manifest: str) -> str:
        if manifest_type:
            normalized = manifest_type.strip().lower()
            if normalized in {"requirements", "requirements.txt", "python"}:
                return "requirements"
            if normalized in {"package", "package.json", "npm"}:
                return "package_json"

        preview = manifest[:200].lower()
        if '"dependencies"' in preview or '"devdependencies"' in preview:
            return "package_json"
        return "requirements"

    def _scan_requirements(self, manifest: str) -> list[dict[str, Any]]:
        issues: list[dict[str, Any]] = []
        lines = manifest.splitlines()
        for idx, line in enumerate(lines, start=1):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            package, version = self._parse_requirement_line(stripped)
            if not package or not version:
                continue
            for rule in self.PY_RULES:
                if package.lower() != rule.package:
                    continue
                if self._is_version_less(version, rule.safe_version):
                    issues.append(self._to_issue(idx, rule, package, version))
        return issues

    def _scan_package_json(self, manifest: str) -> list[dict[str, Any]]:
        try:
            data = json.loads(manifest)
        except json.JSONDecodeError:
            return []
        dependencies = {
            **(data.get("dependencies") or {}),
            **(data.get("devDependencies") or {}),
        }
        issues: list[dict[str, Any]] = []
        for package, raw_version in dependencies.items():
            version = self._extract_semver(str(raw_version))
            if not version:
                continue
            for rule in self.NPM_RULES:
                if package.lower() != rule.package:
                    continue
                if self._is_version_less(version, rule.safe_version):
                    issues.append(self._to_issue(1, rule, package, version))
        return issues

    def _parse_requirement_line(self, line: str) -> tuple[str | None, str | None]:
        match = re.match(r"^([a-zA-Z0-9_.-]+)\s*(==|>=|~=|<=|>|<)\s*([0-9][a-zA-Z0-9_.-]*)", line)
        if not match:
            return None, None
        package = match.group(1).lower()
        version = self._extract_semver(match.group(3))
        return package, version

    def _extract_semver(self, raw: str) -> str | None:
        match = re.search(r"(\d+\.\d+(?:\.\d+)?)", raw)
        return match.group(1) if match else None

    def _is_version_less(self, version: str, safe_version: str) -> bool:
        left = self._version_tuple(version)
        right = self._version_tuple(safe_version)
        return left < right

    def _version_tuple(self, version: str) -> tuple[int, int, int]:
        parts = [int(part) for part in version.split(".") if part.isdigit()]
        while len(parts) < 3:
            parts.append(0)
        return tuple(parts[:3])  # type: ignore[return-value]

    def _to_issue(
        self, line: int, rule: VulnerabilityRule, package: str, version: str
    ) -> dict[str, Any]:
        return {
            "line": line,
            "type": "Security",
            "severity": rule.severity,
            "message": f"{rule.message} ({package}=={version})",
            "suggested_fix": rule.suggested_fix,
            "source": "dependency",
            "confidence": "medium",
        }
