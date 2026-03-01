import asyncio
from typing import Any

from app.core.config import settings
from app.services.llm_provider import LLMProvider, MockProvider, get_llm_provider

SEVERITY_VALUES = {"Critical", "High", "Medium", "Low"}


class AIReviewer:
    def __init__(self, provider: LLMProvider | None = None) -> None:
        self.provider = provider or get_llm_provider()
        self.fallback_provider = MockProvider()
        self.max_retries = max(0, settings.LLM_MAX_RETRIES)
        self.base_backoff = max(0.1, settings.LLM_RETRY_BASE_SECONDS)

    async def review(
        self, code: str, language: str = "python", context: str | None = None
    ) -> dict[str, Any]:
        provider_name = self.provider.__class__.__name__.replace("Provider", "").lower()
        raw: dict[str, Any] | None = None

        for attempt in range(self.max_retries + 1):
            try:
                raw = await self.provider.analyze_code(code=code, language=language, context=context)
                break
            except Exception:
                if attempt >= self.max_retries:
                    raw = None
                    break
                await asyncio.sleep(self.base_backoff * (2**attempt))

        if raw is None:
            raw = await self.fallback_provider.analyze_code(code=code, language=language, context=context)
            provider_name = "mock"

        normalized = self._normalize(raw)
        normalized["provider"] = provider_name
        return normalized

    def _normalize(self, payload: dict[str, Any]) -> dict[str, Any]:
        raw_issues = payload.get("issues", [])
        issues: list[dict[str, Any]] = []
        for issue in raw_issues:
            severity = str(issue.get("severity", "Low")).title()
            if severity not in SEVERITY_VALUES:
                severity = "Low"
            issues.append(
                {
                    "line": issue.get("line"),
                    "type": str(issue.get("type", "General")),
                    "severity": severity,
                    "message": str(issue.get("message", "No message provided.")),
                    "suggested_fix": str(issue.get("suggested_fix", "Review this section.")),
                    "source": str(issue.get("source", "ai")),
                    "confidence": str(issue.get("confidence", "medium")),
                }
            )

        summary = payload.get("summary") or self._build_summary(issues)
        normalized_summary = {
            "critical": int(summary.get("critical", 0)),
            "high": int(summary.get("high", 0)),
            "medium": int(summary.get("medium", 0)),
            "low": int(summary.get("low", 0)),
            "score": int(summary.get("score", 100)),
        }
        normalized_summary["score"] = max(0, min(100, normalized_summary["score"]))

        refactor_suggestions = []
        for item in payload.get("refactor_suggestions", []):
            before = str(item.get("before", "")).strip()
            after = str(item.get("after", "")).strip()
            reason = str(item.get("reason", "Improve readability and safety.")).strip()
            if before and after:
                refactor_suggestions.append({"before": before, "after": after, "reason": reason})

        technical_debt = str(payload.get("technical_debt") or self._debt_label(normalized_summary["score"]))
        overall_assessment = str(
            payload.get("overall_assessment")
            or "Code needs refactoring for maintainability and security hardening."
        )

        return {
            "issues": issues,
            "summary": normalized_summary,
            "technical_debt": technical_debt,
            "overall_assessment": overall_assessment,
            "refactor_suggestions": refactor_suggestions[:8],
        }

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
