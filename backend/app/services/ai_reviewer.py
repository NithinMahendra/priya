import asyncio
import time
from typing import Any

from app.core.config import settings
from app.services.llm_provider import LLMProvider, MockProvider, get_llm_provider

SEVERITY_VALUES = {"Critical", "High", "Medium", "Low"}


class AIReviewer:
    def __init__(self, provider: LLMProvider | None = None) -> None:
        self.provider = provider or get_llm_provider()
        self.fallback_provider = MockProvider()
        self.allow_mock_fallback = settings.LLM_ALLOW_MOCK_FALLBACK
        self.max_retries = max(0, settings.LLM_MAX_RETRIES)
        self.base_backoff = max(0.1, settings.LLM_RETRY_BASE_SECONDS)
        self.total_timeout = max(5.0, settings.LLM_TOTAL_TIMEOUT_SECONDS)

    async def review(
        self, code: str, language: str = "python", context: str | None = None
    ) -> dict[str, Any]:
        started_at = time.monotonic()
        provider_name = self._provider_name()
        line_count = max(1, len(code.splitlines()))
        prompt_constraints = self._build_prompt_constraints(language=language, line_count=line_count)
        merged_context = prompt_constraints if not context else f"{prompt_constraints}\n\n{context}"

        raw: dict[str, Any] | None = None
        last_error: Exception | None = None
        max_attempts = self._max_attempts()
        for attempt in range(max_attempts):
            elapsed = time.monotonic() - started_at
            remaining = self.total_timeout - elapsed
            if remaining <= 0:
                last_error = TimeoutError("LLM review timed out before provider completed.")
                raw = None
                break
            try:
                raw = await asyncio.wait_for(
                    self.provider.analyze_code(code=code, language=language, context=merged_context),
                    timeout=remaining,
                )
                provider_name = self._provider_name()
                break
            except asyncio.TimeoutError:
                last_error = TimeoutError("LLM review timed out.")
                raw = None
                break
            except Exception as exc:
                last_error = exc
                if attempt >= max_attempts - 1:
                    raw = None
                    break
                sleep_for = self.base_backoff * (2**attempt)
                post_error_elapsed = time.monotonic() - started_at
                remaining_after_error = self.total_timeout - post_error_elapsed
                if remaining_after_error <= 0:
                    raw = None
                    break
                await asyncio.sleep(min(sleep_for, remaining_after_error))

        if raw is None:
            if isinstance(self.provider, MockProvider) or self.allow_mock_fallback:
                raw = await self.fallback_provider.analyze_code(
                    code=code, language=language, context=merged_context
                )
                provider_name = "mock"
            else:
                detail = str(last_error) if last_error else "unknown error"
                raise RuntimeError(
                    f"LLM provider failed after retries and mock fallback is disabled. Cause: {detail}"
                )

        normalized = self._normalize(raw, line_count=line_count)
        normalized["provider"] = provider_name
        return normalized

    def _max_attempts(self) -> int:
        provider_cls = self.provider.__class__.__name__.lower()
        if "openrouter" in provider_cls:
            return 1
        return self.max_retries + 1

    def _provider_name(self) -> str:
        dynamic_name = getattr(self.provider, "last_provider_name", None)
        if isinstance(dynamic_name, str) and dynamic_name.strip():
            return dynamic_name.strip().lower()
        return self.provider.__class__.__name__.replace("Provider", "").lower()

    def _build_prompt_constraints(self, language: str, line_count: int) -> str:
        return (
            "Review Constraints:\n"
            f"1) Detect the programming language from code first; language hint is '{language}'.\n"
            "2) Apply language-specific rules (e.g., Java naming, equals usage, exceptions, streams).\n"
            f"3) Validate line numbers against source range 1..{line_count}; omit any invalid line.\n"
            "4) For each actionable issue, include original_code and fixed_code snippets when possible.\n"
            "5) Include performance with time_complexity, space_complexity, confidence, hotspots.\n"
            "6) Return strict JSON only."
        )

    def _normalize(self, payload: dict[str, Any], line_count: int) -> dict[str, Any]:
        if not isinstance(payload, dict):
            payload = {}

        raw_issues = payload.get("issues", [])
        if not isinstance(raw_issues, list):
            raw_issues = []
        issues: list[dict[str, Any]] = []
        for issue in raw_issues:
            if not isinstance(issue, dict):
                continue
            line = self._normalize_line(issue.get("line"), line_count=line_count)
            if issue.get("line") is not None and line is None:
                continue
            severity = str(issue.get("severity", "Low")).title()
            if severity not in SEVERITY_VALUES:
                severity = "Low"
            issues.append(
                {
                    "line": line,
                    "type": str(issue.get("type", "General")),
                    "severity": severity,
                    "message": str(issue.get("message", "No message provided.")),
                    "suggested_fix": str(issue.get("suggested_fix", "Review this section.")),
                    "original_code": self._normalize_snippet(issue.get("original_code")),
                    "fixed_code": self._normalize_snippet(issue.get("fixed_code")),
                    "source": str(issue.get("source", "ai")),
                    "confidence": str(issue.get("confidence", "medium")),
                }
            )

        summary = self._build_summary(issues)

        refactor_suggestions = []
        raw_refactors = payload.get("refactor_suggestions", [])
        if not isinstance(raw_refactors, list):
            raw_refactors = []
        for item in raw_refactors:
            if not isinstance(item, dict):
                continue
            before = str(item.get("before", "")).strip()
            after = str(item.get("after", "")).strip()
            reason = str(item.get("reason", "Improve readability and safety.")).strip()
            if before and after:
                refactor_suggestions.append({"before": before, "after": after, "reason": reason})

        technical_debt = str(payload.get("technical_debt") or self._debt_label(summary["score"]))
        overall_assessment = str(
            payload.get("overall_assessment")
            or "Code needs refactoring for maintainability and security hardening."
        )
        performance = self._normalize_performance(payload.get("performance"), line_count=line_count)

        return {
            "issues": issues,
            "summary": summary,
            "technical_debt": technical_debt,
            "overall_assessment": overall_assessment,
            "refactor_suggestions": refactor_suggestions[:8],
            "performance": performance,
        }

    def _normalize_snippet(self, value: Any) -> str | None:
        if value is None:
            return None
        snippet = str(value).strip()
        return snippet or None

    def _normalize_performance(self, payload: Any, line_count: int) -> dict[str, Any]:
        if not isinstance(payload, dict):
            payload = {}
        raw_hotspots = payload.get("hotspots", [])
        if not isinstance(raw_hotspots, list):
            raw_hotspots = []

        hotspots: list[dict[str, Any]] = []
        for hotspot in raw_hotspots:
            if not isinstance(hotspot, dict):
                continue
            line = self._normalize_line(hotspot.get("line"), line_count=line_count)
            if hotspot.get("line") is not None and line is None:
                continue
            hotspots.append(
                {
                    "line": line,
                    "operation": str(hotspot.get("operation", "Potential hotspot")),
                    "estimated_complexity": str(
                        hotspot.get("estimated_complexity", payload.get("time_complexity", "Unknown"))
                    ),
                    "recommendation": str(
                        hotspot.get("recommendation", "Profile this path with production-like data.")
                    ),
                    "source": str(hotspot.get("source", "ai")),
                }
            )

        confidence = str(payload.get("confidence", "medium")).strip().lower() or "medium"
        if confidence not in {"low", "medium", "high"}:
            confidence = "medium"

        return {
            "time_complexity": str(payload.get("time_complexity", "Unknown")),
            "space_complexity": str(payload.get("space_complexity", "Unknown")),
            "confidence": confidence,
            "hotspots": hotspots[:8],
        }

    def _normalize_line(self, value: Any, line_count: int) -> int | None:
        if value is None:
            return None
        try:
            line = int(value)
        except (TypeError, ValueError):
            return None
        if 1 <= line <= line_count:
            return line
        return None

    def _build_summary(self, issues: list[dict[str, Any]]) -> dict[str, int]:
        counts = {"Critical": 0, "High": 0, "Medium": 0, "Low": 0}
        weights = {"Critical": 25, "High": 15, "Medium": 8, "Low": 3}
        for issue in issues:
            severity = issue.get("severity", "Low")
            if severity in counts:
                counts[severity] += 1
        score = max(0, 100 - sum(counts[s] * weights[s] for s in counts))
        return {
            "critical": counts["Critical"],
            "high": counts["High"],
            "medium": counts["Medium"],
            "low": counts["Low"],
            "score": score,
        }

    def _debt_label(self, score: int) -> str:
        if score >= 90:
            return "Low"
        if score >= 75:
            return "Moderate"
        if score >= 55:
            return "High"
        return "Severe"
