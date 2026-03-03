import re
from typing import Any

from app.core.config import BACKEND_DIR, PROJECT_ROOT
from app.services.ai_reviewer import AIReviewer
from app.services.dependency_scanner import DependencyScanner
from app.services.performance_analyzer import PerformanceAnalyzer
from app.services.project_context import ProjectContextBuilder
from app.services.security_scanner import SecurityScanner
from app.services.static_analyzer import StaticAnalyzer

SEVERITY_RANK = {"Critical": 4, "High": 3, "Medium": 2, "Low": 1}


class ReviewService:
    def __init__(
        self,
        static_analyzer: StaticAnalyzer | None = None,
        security_scanner: SecurityScanner | None = None,
        dependency_scanner: DependencyScanner | None = None,
        performance_analyzer: PerformanceAnalyzer | None = None,
        context_builder: ProjectContextBuilder | None = None,
        ai_reviewer: AIReviewer | None = None,
    ) -> None:
        self.static_analyzer = static_analyzer or StaticAnalyzer()
        self.security_scanner = security_scanner or SecurityScanner()
        self.dependency_scanner = dependency_scanner or DependencyScanner()
        self.performance_analyzer = performance_analyzer or PerformanceAnalyzer()
        self.context_builder = context_builder or ProjectContextBuilder()
        self.ai_reviewer = ai_reviewer or AIReviewer()

    async def run(
        self,
        code: str,
        language: str = "python",
        filename: str | None = None,
        include_project_context: bool = False,
        context_text: str | None = None,
        dependency_manifest: str | None = None,
        manifest_type: str | None = None,
    ) -> dict[str, Any]:
        static_issues = self.static_analyzer.analyze(code=code, language=language, filename=filename)
        security_issues = self.security_scanner.scan(code=code, language=language)

        dependency_issues = self._scan_dependencies(
            code=code,
            filename=filename,
            dependency_manifest=dependency_manifest,
            manifest_type=manifest_type,
            include_project_context=include_project_context,
        )

        context = self._build_review_context(
            include_project_context=include_project_context,
            context_text=context_text,
        )
        ai_error_detail: str | None = None
        try:
            ai_result = await self.ai_reviewer.review(code=code, language=language, context=context)
        except RuntimeError as exc:
            if not self._is_quota_exhaustion_error(str(exc)):
                raise
            ai_error_detail = str(exc)
            ai_result = self._quota_degraded_ai_result(error_detail=ai_error_detail)
        static_performance = self.performance_analyzer.analyze(
            code=code, language=language, filename=filename
        )
        merged_performance = self._merge_performance(
            static_profile=static_performance,
            ai_profile=ai_result.get("performance", {}),
        )

        combined_issues = self._merge_issues(
            static_issues + security_issues + dependency_issues + ai_result["issues"]
        )
        summary = self._build_summary(combined_issues)
        local_refactors = self._generate_local_refactors(code, combined_issues)
        ai_refactors = ai_result.get("refactor_suggestions", [])
        all_refactors = self._merge_refactors(ai_refactors + local_refactors)
        technical_debt = self._technical_debt(summary["score"])
        overall = self._overall_assessment(summary)
        if ai_error_detail:
            overall = (
                "Local-only analysis completed. AI semantic review is unavailable due to OpenRouter "
                "free-tier quota exhaustion."
            )

        return {
            "issues": combined_issues,
            "summary": summary,
            "technical_debt": technical_debt,
            "overall_assessment": overall,
            "refactor_suggestions": all_refactors[:10],
            "provider": ai_result.get("provider", "mock"),
            "performance": merged_performance,
        }

    def _scan_dependencies(
        self,
        code: str,
        filename: str | None,
        dependency_manifest: str | None,
        manifest_type: str | None,
        include_project_context: bool,
    ) -> list[dict[str, Any]]:
        if dependency_manifest:
            return self.dependency_scanner.scan(dependency_manifest, manifest_type=manifest_type)

        if filename and filename.lower() in {"requirements.txt", "package.json"}:
            kind = "requirements" if filename.lower() == "requirements.txt" else "package_json"
            return self.dependency_scanner.scan(code, manifest_type=kind)

        if not include_project_context:
            return []

        collected: list[dict[str, Any]] = []
        local_requirements = BACKEND_DIR / "requirements.txt"
        local_package = PROJECT_ROOT / "frontend" / "package.json"
        if local_requirements.exists():
            content = local_requirements.read_text(encoding="utf-8", errors="ignore")
            collected.extend(self.dependency_scanner.scan(content, manifest_type="requirements"))
        if local_package.exists():
            content = local_package.read_text(encoding="utf-8", errors="ignore")
            collected.extend(self.dependency_scanner.scan(content, manifest_type="package_json"))
        return collected

    def _build_review_context(self, include_project_context: bool, context_text: str | None) -> str | None:
        if not include_project_context and not context_text:
            return None
        return self.context_builder.build(user_context=context_text)

    def _merge_issues(self, issues: list[dict[str, Any]]) -> list[dict[str, Any]]:
        merged: dict[tuple[int | None, str, str], dict[str, Any]] = {}
        for issue in issues:
            key = (
                issue.get("line"),
                str(issue.get("type", "General")),
                str(issue.get("message", "")),
            )
            severity = str(issue.get("severity", "Low")).title()
            if severity not in SEVERITY_RANK:
                severity = "Low"
            candidate = {
                "line": issue.get("line"),
                "type": str(issue.get("type", "General")),
                "severity": severity,
                "message": str(issue.get("message", "Potential issue detected.")),
                "suggested_fix": str(issue.get("suggested_fix", "Inspect and refactor this section.")),
                "original_code": issue.get("original_code"),
                "fixed_code": issue.get("fixed_code"),
                "source": str(issue.get("source", "local")),
                "confidence": str(issue.get("confidence", "medium")),
            }
            if key not in merged:
                merged[key] = candidate
                continue
            current = merged[key]
            if SEVERITY_RANK[candidate["severity"]] > SEVERITY_RANK[current["severity"]]:
                if not candidate.get("original_code"):
                    candidate["original_code"] = current.get("original_code")
                if not candidate.get("fixed_code"):
                    candidate["fixed_code"] = current.get("fixed_code")
                merged[key] = candidate
                continue
            if not current.get("original_code") and candidate.get("original_code"):
                current["original_code"] = candidate["original_code"]
            if not current.get("fixed_code") and candidate.get("fixed_code"):
                current["fixed_code"] = candidate["fixed_code"]

        return sorted(
            merged.values(),
            key=lambda item: (-SEVERITY_RANK[item["severity"]], item.get("line") or 0),
        )

    def _build_summary(self, issues: list[dict[str, Any]]) -> dict[str, int]:
        counts = {"Critical": 0, "High": 0, "Medium": 0, "Low": 0}
        for issue in issues:
            severity = issue.get("severity", "Low")
            if severity in counts:
                counts[severity] += 1

        score = max(
            0,
            100
            - counts["Critical"] * 25
            - counts["High"] * 15
            - counts["Medium"] * 8
            - counts["Low"] * 3,
        )

        return {
            "critical": counts["Critical"],
            "high": counts["High"],
            "medium": counts["Medium"],
            "low": counts["Low"],
            "score": score,
        }

    def _technical_debt(self, score: int) -> str:
        if score >= 90:
            return "Low"
        if score >= 75:
            return "Moderate"
        if score >= 55:
            return "High"
        return "Severe"

    def _overall_assessment(self, summary: dict[str, int]) -> str:
        if summary["critical"] > 0:
            return "Code has critical issues and should not be released before remediation."
        if summary["high"] > 0:
            return "Code needs significant fixes before production use."
        if summary["medium"] > 0:
            return "Code is functional but should be refactored for maintainability."
        return "Code quality is strong with minor improvements suggested."

    def _generate_local_refactors(self, code: str, issues: list[dict[str, Any]]) -> list[dict[str, str]]:
        suggestions: list[dict[str, str]] = []
        lines = code.splitlines()

        for issue in issues:
            line_no = issue.get("line")
            message = issue.get("message", "")
            if not isinstance(line_no, int) or line_no < 1 or line_no > len(lines):
                continue

            before = lines[line_no - 1].strip()
            if "SQL injection" in message:
                suggestions.append(
                    {
                        "before": before,
                        "after": 'cursor.execute("SELECT * FROM table WHERE id = %s", (item_id,))',
                        "reason": "Use parameterized SQL to avoid injection.",
                    }
                )
            elif "eval()" in message:
                suggestions.append(
                    {
                        "before": before,
                        "after": "parsed = json.loads(input_data)",
                        "reason": "Replace eval() with a safe parser.",
                    }
                )
            elif "hardcoded secret" in message.lower():
                variable = self._extract_variable_name(before)
                suggestions.append(
                    {
                        "before": before,
                        "after": f"{variable} = os.getenv('{variable.upper()}', '')",
                        "reason": "Move secrets to environment variables.",
                    }
                )
            elif "ssrf" in message.lower():
                suggestions.append(
                    {
                        "before": before,
                        "after": "validated_url = validate_url(user_url)\nresponse = requests.get(validated_url, timeout=5)",
                        "reason": "Validate outbound destinations to prevent SSRF.",
                    }
                )

        return suggestions

    def _extract_variable_name(self, source_line: str) -> str:
        match = re.match(r"\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*=", source_line)
        if match:
            return match.group(1)
        return "secret_value"

    def _merge_refactors(self, items: list[dict[str, str]]) -> list[dict[str, str]]:
        deduped: list[dict[str, str]] = []
        seen: set[tuple[str, str]] = set()
        for item in items:
            key = (item.get("before", ""), item.get("after", ""))
            if key in seen:
                continue
            if not item.get("before") or not item.get("after"):
                continue
            seen.add(key)
            deduped.append(
                {
                    "before": item["before"],
                    "after": item["after"],
                    "reason": item.get("reason", "Improve code quality and safety."),
                }
            )
        return deduped

    def _merge_performance(
        self,
        static_profile: dict[str, Any],
        ai_profile: dict[str, Any],
    ) -> dict[str, Any]:
        static_time = str(static_profile.get("time_complexity", "Unknown"))
        ai_time = str(ai_profile.get("time_complexity", "Unknown"))
        static_space = str(static_profile.get("space_complexity", "Unknown"))
        ai_space = str(ai_profile.get("space_complexity", "Unknown"))

        merged_time = ai_time if self._complexity_rank(ai_time) >= self._complexity_rank(static_time) else static_time
        merged_space = ai_space if self._complexity_rank(ai_space) >= self._complexity_rank(static_space) else static_space

        hotspots: list[dict[str, Any]] = []
        for source in [static_profile.get("hotspots", []), ai_profile.get("hotspots", [])]:
            if not isinstance(source, list):
                continue
            for item in source:
                if not isinstance(item, dict):
                    continue
                hotspots.append(
                    {
                        "line": item.get("line"),
                        "operation": str(item.get("operation", "Potential hotspot")),
                        "estimated_complexity": str(
                            item.get("estimated_complexity", item.get("complexity", merged_time))
                        ),
                        "recommendation": str(
                            item.get("recommendation", "Profile and optimize this path.")
                        ),
                        "source": str(item.get("source", "static")),
                    }
                )

        confidence = str(ai_profile.get("confidence", static_profile.get("confidence", "medium"))).lower()
        if confidence not in {"low", "medium", "high"}:
            confidence = "medium"

        return {
            "time_complexity": merged_time,
            "space_complexity": merged_space,
            "confidence": confidence,
            "hotspots": hotspots[:10],
        }

    def _complexity_rank(self, complexity: str) -> int:
        value = complexity.lower().replace(" ", "")
        if "n!" in value:
            return 8
        if "2^n" in value:
            return 7
        if "n^k" in value:
            return 6
        if "n^3" in value:
            return 5
        if "n^2" in value:
            return 4
        if "nlogn" in value:
            return 3
        if "o(n)" in value:
            return 2
        if "logn" in value:
            return 1
        if "o(1)" in value:
            return 0
        return 1

    def _is_quota_exhaustion_error(self, detail: str) -> bool:
        lowered = detail.lower()
        return (
            "free-models-per-day" in lowered
            or "rate limit exceeded" in lowered
            or "code=429" in lowered
            or "openrouter error 429" in lowered
        )

    def _quota_degraded_ai_result(self, error_detail: str) -> dict[str, Any]:
        message = (
            "AI semantic review unavailable: OpenRouter free-tier daily quota reached. "
            "Returning local static/security analysis only."
        )
        return {
            "issues": [
                {
                    "line": None,
                    "type": "Availability",
                    "severity": "Low",
                    "message": message,
                    "suggested_fix": "Wait for daily quota reset or add OpenRouter credits.",
                    "source": "ai",
                    "confidence": "high",
                    "original_code": None,
                    "fixed_code": None,
                }
            ],
            "summary": {"critical": 0, "high": 0, "medium": 0, "low": 1, "score": 97},
            "technical_debt": "Low",
            "overall_assessment": message,
            "refactor_suggestions": [],
            "provider": f"openrouter-quota-degraded: {error_detail[:180]}",
            "performance": {
                "time_complexity": "Unknown",
                "space_complexity": "Unknown",
                "confidence": "low",
                "hotspots": [],
            },
        }
