import re
from dataclasses import dataclass
from typing import Any


@dataclass
class SecurityIssue:
    line: int | None
    severity: str
    message: str
    suggested_fix: str
    confidence: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "line": self.line,
            "type": "Security",
            "severity": self.severity,
            "message": self.message,
            "suggested_fix": self.suggested_fix,
            "source": "security",
            "confidence": self.confidence,
        }


class SecurityScanner:
    def __init__(self) -> None:
        self.high_signal_patterns: list[tuple[re.Pattern[str], str, str, str]] = [
            (
                re.compile(r"\beval\s*\(", re.IGNORECASE),
                "High",
                "Use of eval() can lead to arbitrary code execution.",
                "Replace eval() with safe parsers or explicit mappings.",
            ),
            (
                re.compile(r"\b(exec|Runtime\.getRuntime\(\)\.exec)\s*\(", re.IGNORECASE),
                "High",
                "Dynamic command execution detected.",
                "Validate command inputs and avoid shell command construction with user data.",
            ),
            (
                re.compile(r"\b(pickle\.loads|yaml\.load\s*\(|ObjectInputStream\s*\()", re.IGNORECASE),
                "High",
                "Insecure deserialization pattern detected.",
                "Use safe deserialization APIs and strict type validation.",
            ),
            (
                re.compile(r"\b(subprocess\.\w+\(.*shell\s*=\s*True|os\.system\s*\()", re.IGNORECASE),
                "High",
                "Unsafe subprocess invocation detected.",
                "Avoid shell=True and pass command arguments as a list.",
            ),
            (
                re.compile(r"\b(api[_-]?key|secret|token)\b\s*[:=]\s*['\"][^'\"]{12,}['\"]", re.IGNORECASE),
                "High",
                "Hardcoded API key or secret detected.",
                "Store secrets in environment variables or managed secret stores.",
            ),
        ]
        self.sql_keywords = re.compile(r"\b(SELECT|INSERT|UPDATE|DELETE)\b", re.IGNORECASE)
        self.dynamic_query_signal = re.compile(r"(\+|%s|format\(|\{[^}]+\})")
        self.ssrf_signal = re.compile(
            r"\b(requests\.(get|post|put|delete)|httpx\.(get|post)|axios\.(get|post)|fetch\s*\(|URL\s*\()",
            re.IGNORECASE,
        )
        self.user_input_signal = re.compile(
            r"\b(user_input|request\.(args|query_params|get_json)|req\.(query|body)|input|argv)\b",
            re.IGNORECASE,
        )

    def scan(self, code: str, language: str = "python") -> list[dict[str, Any]]:
        lines = code.splitlines()
        findings: list[SecurityIssue] = []
        seen: set[tuple[int | None, str]] = set()

        for idx, line in enumerate(lines, start=1):
            findings.extend(self._scan_high_signal_patterns(idx, line, seen))
            findings.extend(self._scan_sql_injection(idx, line, seen))
            findings.extend(self._scan_ssrf(idx, line, seen))

        return [issue.to_dict() for issue in findings]

    def _scan_high_signal_patterns(
        self, idx: int, line: str, seen: set[tuple[int | None, str]]
    ) -> list[SecurityIssue]:
        issues: list[SecurityIssue] = []
        for pattern, severity, message, suggested_fix in self.high_signal_patterns:
            if not pattern.search(line):
                continue
            key = (idx, message)
            if key in seen:
                continue
            seen.add(key)
            issues.append(
                SecurityIssue(
                    line=idx,
                    severity=severity,
                    message=message,
                    suggested_fix=suggested_fix,
                    confidence="high",
                )
            )
        return issues

    def _scan_sql_injection(self, idx: int, line: str, seen: set[tuple[int | None, str]]) -> list[SecurityIssue]:
        if not self.sql_keywords.search(line):
            return []
        if not self.dynamic_query_signal.search(line):
            return []

        message = "Possible SQL injection pattern in dynamic SQL construction."
        key = (idx, message)
        if key in seen:
            return []
        seen.add(key)
        severity = "Critical" if "+" in line or "format(" in line else "High"
        return [
            SecurityIssue(
                line=idx,
                severity=severity,
                message=message,
                suggested_fix="Use prepared statements / parameterized queries.",
                confidence="medium",
            )
        ]

    def _scan_ssrf(self, idx: int, line: str, seen: set[tuple[int | None, str]]) -> list[SecurityIssue]:
        if not self.ssrf_signal.search(line):
            return []
        if not self.user_input_signal.search(line):
            return []

        message = "Potential SSRF risk: outbound request appears to use untrusted input."
        key = (idx, message)
        if key in seen:
            return []
        seen.add(key)
        return [
            SecurityIssue(
                line=idx,
                severity="High",
                message=message,
                suggested_fix="Validate destination host against an allowlist and block internal/private IP ranges.",
                confidence="medium",
            )
        ]
