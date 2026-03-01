import json
from abc import ABC, abstractmethod
from typing import Any

from app.core.config import settings


class LLMProvider(ABC):
    @abstractmethod
    async def analyze_code(self, code: str, language: str = "python") -> dict[str, Any]:
        """Run semantic analysis and return structured review JSON."""


class MockProvider(LLMProvider):
    def __init__(self, model: str = "mock-model") -> None:
        self.model = model

    async def analyze_code(self, code: str, language: str = "python") -> dict[str, Any]:
        issues: list[dict[str, Any]] = []
        refactor_suggestions: list[dict[str, str]] = []
        lines = code.splitlines()

        for idx, line in enumerate(lines, start=1):
            if "eval(" in line:
                issues.append(
                    {
                        "line": idx,
                        "type": "Security",
                        "severity": "High",
                        "message": "Use of eval() found; this may execute untrusted input.",
                        "suggested_fix": "Replace eval() with safe parsing or explicit mappings.",
                        "source": "ai",
                    }
                )
                refactor_suggestions.append(
                    {
                        "before": line.strip(),
                        "after": "value = safe_parse(user_input)",
                        "reason": "Avoid executing arbitrary expressions via eval().",
                    }
                )
            if "SELECT" in line.upper() and "+" in line:
                issues.append(
                    {
                        "line": idx,
                        "type": "Security",
                        "severity": "Critical",
                        "message": "Possible SQL injection vulnerability.",
                        "suggested_fix": "Use parameterized queries.",
                        "source": "ai",
                    }
                )
                refactor_suggestions.append(
                    {
                        "before": line.strip(),
                        "after": 'cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))',
                        "reason": "Parameterized queries mitigate SQL injection.",
                    }
                )

        if len(lines) > 120:
            issues.append(
                {
                    "line": 1,
                    "type": "Maintainability",
                    "severity": "Medium",
                    "message": "Large file size may impact maintainability.",
                    "suggested_fix": "Split large module into focused components.",
                    "source": "ai",
                }
            )

        if not issues:
            issues.append(
                {
                    "line": 1,
                    "type": "Style",
                    "severity": "Low",
                    "message": "No major semantic issues detected in mock review.",
                    "suggested_fix": "Add domain-specific tests to validate behavior.",
                    "source": "ai",
                }
            )

        summary = _build_summary(issues)
        return {
            "issues": issues,
            "summary": summary,
            "technical_debt": _technical_debt_from_score(summary["score"]),
            "overall_assessment": _overall_assessment(summary),
            "refactor_suggestions": refactor_suggestions[:5],
        }


class OpenAIProvider(LLMProvider):
    def __init__(self, api_key: str, model: str) -> None:
        self.api_key = api_key
        self.model = model

    async def analyze_code(self, code: str, language: str = "python") -> dict[str, Any]:
        try:
            from openai import AsyncOpenAI
        except ImportError as exc:
            raise RuntimeError("OpenAI SDK is not installed.") from exc

        client = AsyncOpenAI(api_key=self.api_key)
        system_prompt = (
            "You are an expert software reviewer. Return valid JSON only with keys: "
            "issues, summary, technical_debt, overall_assessment, refactor_suggestions. "
            "Each issue must include line, type, severity (Critical/High/Medium/Low), "
            "message, suggested_fix."
        )
        user_prompt = (
            f"Language: {language}\n"
            "Analyze this source code for correctness, maintainability, performance, and security.\n"
            "Provide concise, actionable findings.\n\n"
            f"Code:\n```{language}\n{code}\n```"
        )

        response = await client.chat.completions.create(
            model=self.model,
            temperature=0.1,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )

        content = response.choices[0].message.content if response.choices else "{}"
        try:
            return json.loads(content or "{}")
        except json.JSONDecodeError:
            raise RuntimeError("OpenAI response was not valid JSON.")


def build_provider(provider_name: str, api_key: str | None, model: str) -> LLMProvider:
    normalized = (provider_name or "").strip().lower()
    if normalized == "openai" and api_key:
        return OpenAIProvider(api_key=api_key, model=model)
    return MockProvider(model=model)


def get_llm_provider() -> LLMProvider:
    return build_provider(
        provider_name=settings.effective_llm_provider,
        api_key=settings.OPENAI_API_KEY,
        model=settings.LLM_MODEL,
    )


def _build_summary(issues: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"Critical": 0, "High": 0, "Medium": 0, "Low": 0}
    weights = {"Critical": 25, "High": 15, "Medium": 8, "Low": 3}

    for issue in issues:
        severity = str(issue.get("severity", "Low"))
        if severity in counts:
            counts[severity] += 1

    deduction = sum(counts[key] * weights[key] for key in counts)
    score = max(0, min(100, 100 - deduction))
    return {
        "critical": counts["Critical"],
        "high": counts["High"],
        "medium": counts["Medium"],
        "low": counts["Low"],
        "score": score,
    }


def _technical_debt_from_score(score: int) -> str:
    if score >= 90:
        return "Low"
    if score >= 75:
        return "Moderate"
    if score >= 55:
        return "High"
    return "Severe"


def _overall_assessment(summary: dict[str, int]) -> str:
    if summary["critical"] > 0:
        return "Critical risks found. Immediate remediation is required before deployment."
    if summary["high"] > 0:
        return "Code has significant issues and should be revised before release."
    if summary["medium"] > 0:
        return "Code quality is acceptable but refactoring is recommended."
    return "Code is in good condition with minor improvements suggested."
