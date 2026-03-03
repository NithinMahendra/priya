import asyncio
import json
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class LLMProvider(ABC):
    @abstractmethod
    async def analyze_code(
        self, code: str, language: str = "python", context: str | None = None
    ) -> dict[str, Any]:
        pass


class MockProvider(LLMProvider):
    def __init__(self, model: str = "mock-model") -> None:
        self.model = model

    async def analyze_code(
        self, code: str, language: str = "python", context: str | None = None
    ) -> dict[str, Any]:
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

        summary = _build_summary(issues)
        return {
            "issues": issues,
            "summary": summary,
            "technical_debt": _technical_debt_from_score(summary["score"]),
            "overall_assessment": _overall_assessment(summary),
            "refactor_suggestions": refactor_suggestions[:5],
        }


@dataclass
class ModelRateState:
    limit_requests: int | None = None
    remaining_requests: int | None = None
    reset_at: float | None = None
    blocked_until: float | None = None


class OpenRouterProvider(LLMProvider):
    def __init__(
        self,
        api_key: str,
        model: str,
        api_base: str = "https://openrouter.ai/api/v1",
        free_only: bool = True,
        app_name: str | None = None,
        site_url: str | None = None,
        model_cache_seconds: int = 300,
        timeout_seconds: float = 45.0,
    ) -> None:
        self.api_key = api_key
        self.model = model.strip() or "auto"
        self.api_base = api_base.rstrip("/")
        self.free_only = free_only
        self.app_name = app_name
        self.site_url = site_url
        self.model_cache_seconds = max(30, model_cache_seconds)
        self.timeout_seconds = max(10.0, timeout_seconds)
        self.last_provider_name = "openrouter"
        self.last_model = self.model
        self._models_cache: list[dict[str, Any]] = []
        self._models_cached_at = 0.0
        self._models_lock = asyncio.Lock()
        self._rate_state_by_model: dict[str, ModelRateState] = {}
        self._request_timestamps: list[float] = []

    async def analyze_code(
        self, code: str, language: str = "python", context: str | None = None
    ) -> dict[str, Any]:
        system_prompt, user_prompt = _build_prompts(code=code, language=language, context=context)
        needed_tokens = _estimate_tokens(system_prompt) + _estimate_tokens(user_prompt)
        candidates = await self._pick_candidate_models(needed_tokens=needed_tokens)
        if not candidates:
            raise RuntimeError("No eligible OpenRouter models are available.")
        logger.info(
            "openrouter_candidates_selected model_mode=%s needed_tokens=%s candidate_count=%s top_candidates=%s",
            self.model,
            needed_tokens,
            len(candidates),
            candidates[:3],
        )

        errors: list[str] = []
        for index, model_id in enumerate(candidates):
            fallback_attempted = index > 0
            try:
                raw_content = await self._run_completion(
                    model_id=model_id,
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    fallback_attempted=fallback_attempted,
                )
                self.last_model = model_id
                self.last_provider_name = "openrouter"
                logger.info(
                    "openrouter_review_success model=%s candidate_index=%s fallback_attempted=%s",
                    model_id,
                    index,
                    fallback_attempted,
                )
                return _parse_json_content(raw_content, "OpenRouter")
            except _RateLimitedError as exc:
                self._mark_rate_limited(model_id=model_id, retry_after_seconds=exc.retry_after_seconds)
                logger.warning(
                    "openrouter_model_rate_limited model=%s candidate_index=%s retry_after_seconds=%s",
                    model_id,
                    index,
                    exc.retry_after_seconds,
                )
                errors.append(f"{model_id}: {exc}")
            except Exception as exc:
                logger.warning(
                    "openrouter_model_failed model=%s candidate_index=%s fallback_attempted=%s error=%s",
                    model_id,
                    index,
                    fallback_attempted,
                    exc,
                )
                errors.append(f"{model_id}: {exc}")

        raise RuntimeError(
            "OpenRouter failed across candidate models. "
            f"Tried {len(candidates)} models. Details: {' | '.join(errors[:5])}"
        )

    async def _pick_candidate_models(self, needed_tokens: int) -> list[str]:
        if self.model.lower() not in {"", "auto"}:
            if self.free_only:
                try:
                    catalog = await self._get_models()
                except Exception:
                    lowered = self.model.lower()
                    if not (lowered.endswith(":free") or lowered == "openrouter/free"):
                        raise RuntimeError(
                            f"Cannot verify pricing for '{self.model}'. "
                            "Use a :free model or LLM_MODEL=auto when OPENROUTER_FREE_ONLY=true."
                        )
                else:
                    matched = next((item for item in catalog if str(item.get("id", "")) == self.model), None)
                    if matched and not _is_free_model(matched):
                        raise RuntimeError(
                            f"Configured OpenRouter model '{self.model}' is not free. "
                            "Use a :free model or keep LLM_MODEL=auto."
                        )
            return [self.model]

        models = await self._get_models()
        if not models:
            return ["openrouter/free"] if self.free_only else ["openrouter/auto"]

        now = time.time()
        scored: list[tuple[float, str]] = []
        for item in models:
            model_id = str(item.get("id", "")).strip()
            if not model_id:
                continue
            if self.free_only and not _is_free_model(item):
                continue

            context_length = _as_int(item.get("context_length")) or 0
            if context_length > 0 and needed_tokens + 512 > context_length:
                continue

            if _model_blocked(self._rate_state_by_model.get(model_id), now):
                continue

            score = self._score_model(item=item, needed_tokens=needed_tokens, now=now)
            scored.append((score, model_id))

        scored.sort(key=lambda pair: pair[0], reverse=True)
        if scored:
            return [model_id for _, model_id in scored[:8]]

        return ["openrouter/free"] if self.free_only else ["openrouter/auto"]

    def _score_model(self, item: dict[str, Any], needed_tokens: int, now: float) -> float:
        model_id = str(item.get("id", ""))
        context_length = _as_int(item.get("context_length")) or 0
        score = float(min(context_length, 300000)) / 10000.0

        lowered = model_id.lower()
        if lowered.endswith(":free"):
            score += 30.0
        if "coder" in lowered or "code" in lowered:
            score += 25.0
        if "qwen" in lowered:
            score += 8.0
        if "deepseek" in lowered:
            score += 7.0
        if "gpt-oss" in lowered:
            score += 10.0
        if "openrouter/free" in lowered:
            score -= 5.0

        limits = item.get("per_request_limits")
        if isinstance(limits, dict):
            max_prompt = _as_int(
                limits.get("max_prompt_tokens")
                or limits.get("prompt_tokens")
                or limits.get("max_input_tokens")
            )
            if max_prompt and needed_tokens > max_prompt:
                return float("-inf")

        rate = self._rate_state_by_model.get(model_id)
        if rate:
            if rate.remaining_requests is not None:
                score += min(20, rate.remaining_requests) * 0.6
            if rate.limit_requests and rate.remaining_requests is not None and rate.limit_requests > 0:
                headroom = rate.remaining_requests / rate.limit_requests
                score += max(-10.0, min(15.0, 15.0 * headroom))
            if rate.reset_at and rate.reset_at > now:
                score -= min(60.0, rate.reset_at - now) / 6.0

        local_rpm = self._local_requests_per_minute(now)
        if rate and rate.limit_requests and local_rpm >= rate.limit_requests:
            score -= 20.0

        return score

    async def _run_completion(
        self,
        model_id: str,
        system_prompt: str,
        user_prompt: str,
        fallback_attempted: bool,
    ) -> str:
        self._record_request_now()
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        if self.site_url:
            headers["HTTP-Referer"] = self.site_url
        if self.app_name:
            headers["X-Title"] = self.app_name

        payload = {
            "model": model_id,
            "temperature": 0.1,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }

        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.post(
                f"{self.api_base}/chat/completions",
                headers=headers,
                json=payload,
            )

        self._apply_rate_headers(model_id=model_id, headers=response.headers)
        rate_snapshot = _rate_header_snapshot(response.headers)

        if response.status_code == 429:
            retry_after = _retry_after_seconds(response.headers)
            logger.warning(
                "openrouter_429 model=%s fallback_attempted=%s retry_after_seconds=%s rate_headers=%s",
                model_id,
                fallback_attempted,
                retry_after,
                rate_snapshot,
            )
            raise _RateLimitedError(
                message=_extract_error_message(response),
                retry_after_seconds=retry_after,
            )
        if response.status_code >= 400:
            detail = _extract_error_message(response)
            logger.warning(
                "openrouter_http_error model=%s status=%s fallback_attempted=%s rate_headers=%s detail=%s",
                model_id,
                response.status_code,
                fallback_attempted,
                rate_snapshot,
                detail,
            )
            raise RuntimeError(f"OpenRouter error {response.status_code}: {detail}")

        body = response.json()
        choices = body.get("choices") or []
        if not choices:
            raise RuntimeError("OpenRouter response did not include choices.")
        message = choices[0].get("message") or {}
        content = message.get("content")
        if isinstance(content, list):
            chunks = [str(part.get("text", "")) for part in content if isinstance(part, dict)]
            content = "\n".join(chunk for chunk in chunks if chunk).strip()
        if not isinstance(content, str) or not content.strip():
            raise RuntimeError("OpenRouter response did not include textual JSON content.")
        logger.info(
            "openrouter_response_ok model=%s fallback_attempted=%s rate_headers=%s",
            model_id,
            fallback_attempted,
            rate_snapshot,
        )
        return content

    async def _get_models(self) -> list[dict[str, Any]]:
        now = time.time()
        if self._models_cache and (now - self._models_cached_at) <= self.model_cache_seconds:
            return self._models_cache
        async with self._models_lock:
            now = time.time()
            if self._models_cache and (now - self._models_cached_at) <= self.model_cache_seconds:
                return self._models_cache

            headers = {"Authorization": f"Bearer {self.api_key}"}
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.get(f"{self.api_base}/models", headers=headers)

            if response.status_code >= 400:
                if self._models_cache:
                    return self._models_cache
                raise RuntimeError(
                    f"OpenRouter model catalog request failed ({response.status_code})."
                )

            payload = response.json()
            data = payload.get("data")
            if not isinstance(data, list):
                raise RuntimeError("OpenRouter model catalog format is invalid.")
            self._models_cache = [item for item in data if isinstance(item, dict)]
            self._models_cached_at = time.time()
            return self._models_cache

    def _record_request_now(self) -> None:
        now = time.time()
        self._request_timestamps.append(now)
        cutoff = now - 60.0
        self._request_timestamps = [ts for ts in self._request_timestamps if ts >= cutoff]

    def _local_requests_per_minute(self, now: float) -> int:
        cutoff = now - 60.0
        self._request_timestamps = [ts for ts in self._request_timestamps if ts >= cutoff]
        return len(self._request_timestamps)

    def _apply_rate_headers(self, model_id: str, headers: httpx.Headers) -> None:
        state = self._rate_state_by_model.get(model_id, ModelRateState())
        state.limit_requests = _first_int(
            headers,
            [
                "x-ratelimit-limit-requests",
                "x-ratelimit-limit",
                "ratelimit-limit",
            ],
            fallback=state.limit_requests,
        )
        state.remaining_requests = _first_int(
            headers,
            [
                "x-ratelimit-remaining-requests",
                "x-ratelimit-remaining",
                "ratelimit-remaining",
            ],
            fallback=state.remaining_requests,
        )
        reset_value = _first_float(
            headers,
            [
                "x-ratelimit-reset-requests",
                "x-ratelimit-reset",
                "ratelimit-reset",
            ],
            fallback=None,
        )
        if reset_value is not None:
            if reset_value > 1_000_000_000:
                state.reset_at = reset_value
            else:
                state.reset_at = time.time() + max(0.0, reset_value)
        if state.remaining_requests is not None and state.remaining_requests <= 0:
            delay = _retry_after_seconds(headers) or 10.0
            state.blocked_until = time.time() + delay
        self._rate_state_by_model[model_id] = state
        logger.info(
            "openrouter_rate_state_updated model=%s limit_requests=%s remaining_requests=%s reset_at=%s blocked_until=%s",
            model_id,
            state.limit_requests,
            state.remaining_requests,
            state.reset_at,
            state.blocked_until,
        )

    def _mark_rate_limited(self, model_id: str, retry_after_seconds: float | None) -> None:
        state = self._rate_state_by_model.get(model_id, ModelRateState())
        delay = retry_after_seconds if retry_after_seconds is not None else 12.0
        now = time.time()
        state.remaining_requests = 0
        state.blocked_until = now + max(1.0, delay)
        if state.reset_at is None or state.reset_at < state.blocked_until:
            state.reset_at = state.blocked_until
        self._rate_state_by_model[model_id] = state


class _RateLimitedError(Exception):
    def __init__(self, message: str, retry_after_seconds: float | None) -> None:
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds


def _build_prompts(code: str, language: str, context: str | None) -> tuple[str, str]:
    system_prompt = (
        "You are an expert software reviewer. Return valid JSON only with keys: "
        "issues, summary, technical_debt, overall_assessment, refactor_suggestions. "
        "Each issue must include line, type, severity (Critical/High/Medium/Low), message, suggested_fix."
    )
    context_block = (context or "No repository context provided.").strip()[:3500]
    user_prompt = (
        f"Language hint: {language}\n"
        "Analyze this source code for correctness, maintainability, performance, and security.\n"
        "Use repository context to infer architectural intent when relevant.\n\n"
        f"Repository Context:\n{context_block}\n\n"
        f"Code:\n```{language}\n{code}\n```"
    )
    return system_prompt, user_prompt


def _parse_json_content(content: str | None, provider_label: str) -> dict[str, Any]:
    try:
        return json.loads(content or "{}")
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"{provider_label} response was not valid JSON.") from exc


def _estimate_tokens(text: str) -> int:
    return max(1, int(len(text) / 4))


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return None


def _as_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return None


def _is_free_model(item: dict[str, Any]) -> bool:
    model_id = str(item.get("id", "")).lower()
    if model_id.endswith(":free") or model_id == "openrouter/free":
        return True
    pricing = item.get("pricing")
    if not isinstance(pricing, dict):
        return False
    prompt_price = _as_float(pricing.get("prompt"))
    completion_price = _as_float(pricing.get("completion"))
    if prompt_price is None or completion_price is None:
        return False
    return prompt_price <= 0 and completion_price <= 0


def _model_blocked(state: ModelRateState | None, now: float) -> bool:
    if not state:
        return False
    if state.blocked_until and state.blocked_until > now:
        return True
    return False


def _extract_error_message(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except Exception:
        text = response.text.strip()
        return text[:500] if text else f"HTTP {response.status_code}"
    if isinstance(payload, dict):
        err = payload.get("error")
        if isinstance(err, dict):
            message = err.get("message")
            if message:
                return str(message)
        if isinstance(err, str):
            return err
        detail = payload.get("detail")
        if detail:
            return str(detail)
    return f"HTTP {response.status_code}"


def _retry_after_seconds(headers: httpx.Headers) -> float | None:
    retry_after = headers.get("retry-after")
    if retry_after is None:
        return None
    try:
        return max(0.0, float(retry_after))
    except (TypeError, ValueError):
        return None


def _rate_header_snapshot(headers: httpx.Headers) -> dict[str, str | None]:
    keys = [
        "x-ratelimit-limit-requests",
        "x-ratelimit-remaining-requests",
        "x-ratelimit-reset-requests",
        "x-ratelimit-limit",
        "x-ratelimit-remaining",
        "x-ratelimit-reset",
        "ratelimit-limit",
        "ratelimit-remaining",
        "ratelimit-reset",
        "retry-after",
    ]
    snapshot: dict[str, str | None] = {}
    for key in keys:
        value = headers.get(key)
        if value is not None:
            snapshot[key] = value
    return snapshot


def _first_int(headers: httpx.Headers, names: list[str], fallback: int | None) -> int | None:
    for name in names:
        value = headers.get(name)
        if value is None:
            continue
        parsed = _as_int(value)
        if parsed is not None:
            return parsed
    return fallback


def _first_float(headers: httpx.Headers, names: list[str], fallback: float | None) -> float | None:
    for name in names:
        value = headers.get(name)
        if value is None:
            continue
        parsed = _as_float(value)
        if parsed is not None:
            return parsed
    return fallback


def _validate_openrouter_api_key(api_key: str | None) -> str:
    key = (api_key or "").strip()
    if not key:
        raise ValueError("LLM_PROVIDER=openrouter requires OPENROUTER_API_KEY.")
    return key


def _model_for_openrouter(requested_model: str) -> str:
    model = (requested_model or "").strip()
    if not model:
        return "auto"
    return model


def build_provider(
    provider_name: str,
    openrouter_api_key: str | None,
    model: str,
    api_base: str = "https://openrouter.ai/api/v1",
    free_only: bool = True,
    app_name: str | None = None,
    site_url: str | None = None,
    model_cache_seconds: int = 300,
    timeout_seconds: float = 45.0,
) -> LLMProvider:
    provider = (provider_name or "").strip().lower()
    resolved_model = _model_for_openrouter(model)
    if provider in {"", "auto"}:
        key = (openrouter_api_key or "").strip()
        if key:
            return OpenRouterProvider(
                api_key=key,
                model=resolved_model,
                api_base=api_base,
                free_only=free_only,
                app_name=app_name,
                site_url=site_url,
                model_cache_seconds=model_cache_seconds,
                timeout_seconds=timeout_seconds,
            )
        return MockProvider(model=resolved_model)
    if provider == "mock":
        return MockProvider(model=resolved_model)
    if provider == "openrouter":
        return OpenRouterProvider(
            api_key=_validate_openrouter_api_key(openrouter_api_key),
            model=resolved_model,
            api_base=api_base,
            free_only=free_only,
            app_name=app_name,
            site_url=site_url,
            model_cache_seconds=model_cache_seconds,
            timeout_seconds=timeout_seconds,
        )
    raise ValueError("LLM_PROVIDER must be 'auto', 'openrouter', or 'mock'.")


def get_llm_provider() -> LLMProvider:
    return build_provider(
        provider_name=settings.LLM_PROVIDER,
        openrouter_api_key=settings.OPENROUTER_API_KEY,
        model=settings.LLM_MODEL,
        api_base=settings.OPENROUTER_API_BASE,
        free_only=settings.OPENROUTER_FREE_ONLY,
        app_name=settings.OPENROUTER_APP_NAME,
        site_url=settings.OPENROUTER_SITE_URL,
        model_cache_seconds=settings.OPENROUTER_MODEL_CACHE_SECONDS,
        timeout_seconds=settings.OPENROUTER_TIMEOUT_SECONDS,
    )


def get_provider_diagnostics() -> dict[str, Any]:
    configured = settings.LLM_PROVIDER.strip().lower()
    key_present = bool((settings.OPENROUTER_API_KEY or "").strip())
    if configured == "openrouter":
        provider = "openrouter"
    elif configured in {"", "auto"} and key_present:
        provider = "openrouter"
    else:
        provider = "mock"
    effective = settings.effective_llm_provider
    if effective not in {"openrouter", "mock"}:
        effective = "mock"
    model_mode = (settings.LLM_MODEL or "").strip() or "auto"
    parsed = urlparse(settings.OPENROUTER_API_BASE)
    api_base_host = parsed.hostname or "openrouter.ai"
    return {
        "provider": provider,
        "effective_provider": effective,
        "model_mode": model_mode,
        "free_only": bool(settings.OPENROUTER_FREE_ONLY),
        "api_base_host": api_base_host,
        "mock_fallback_allowed": bool(settings.LLM_ALLOW_MOCK_FALLBACK),
    }


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
