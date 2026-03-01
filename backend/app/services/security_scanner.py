import re
from dataclasses import dataclass
from typing import Any


@dataclass
class SecurityIssue:
    line: int | None
    severity: str
    message: str
    suggested_fix: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "line": self.line,
            "type": "Security",
            "severity": self.severity,
            "message": self.message,
            "suggested_fix": self.suggested_fix,
            "source": "security",
        }


class SecurityScanner:
    def __init__(self) -> None:
        self.patterns: list[tuple[re.Pattern[str], str, str, str]] = [
            (
                re.compile(r"execute\s*\(\s*.*(\+|%|\{).*", re.IGNORECASE),
                "Critical",
                "Potential SQL injection via dynamic query construction.",
                "Use parameterized queries with bound parameters.",
            ),
            (
                re.compile(r"(SELECT|INSERT|UPDATE|DELETE).*(\+|\{)", re.IGNORECASE),
                "High",
                "Possible SQL injection pattern in SQL string assembly.",
                "Construct SQL with parameters instead of string concatenation.",
            ),
            (
                re.compile(r"\beval\s*\(", re.IGNORECASE),
                "High",
                "Use of eval() can lead to arbitrary code execution.",
                "Replace eval() with safe parsing or explicit logic.",
            ),
            (
                re.compile(r"\b(api[_-]?key|secret|token)\b\s*=\s*['\"][^'\"]{12,}['\"]", re.IGNORECASE),
                "High",
                "Hardcoded API key or secret detected.",
                "Store secrets in environment variables or vault services.",
            ),
            (
                re.compile(r"\b(pickle\.loads|yaml\.load\s*\()", re.IGNORECASE),
                "High",
                "Insecure deserialization pattern detected.",
                "Use safe deserialization methods, e.g. yaml.safe_load.",
            ),
            (
                re.compile(r"\b(subprocess\.\w+\(.*shell\s*=\s*True|os\.system\s*\()", re.IGNORECASE),
                "High",
                "Unsafe subprocess invocation detected.",
                "Avoid shell=True and pass command arguments as a list.",
            ),
        ]

    def scan(self, code: str, language: str = "python") -> list[dict[str, Any]]:
        lines = code.splitlines()
        findings: list[SecurityIssue] = []
        seen: set[tuple[int | None, str]] = set()

        for idx, line in enumerate(lines, start=1):
            for pattern, severity, message, suggested_fix in self.patterns:
                if pattern.search(line):
                    key = (idx, message)
                    if key in seen:
                        continue
                    seen.add(key)
                    findings.append(
                        SecurityIssue(
                            line=idx,
                            severity=severity,
                            message=message,
                            suggested_fix=suggested_fix,
                        )
                    )

        return [issue.to_dict() for issue in findings]
