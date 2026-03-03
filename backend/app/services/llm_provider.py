import asyncio
import json
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from functools import lru_cache
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

    async def generate_json(self, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        raise NotImplementedError("Provider does not support generic JSON generation.")


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
                        "original_code": line.strip(),
                        "fixed_code": "value = safe_parse(user_input)",
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
                        "original_code": line.strip(),
                        "fixed_code": 'cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))',
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
            "performance": {
                "time_complexity": "O(n^2)" if any("for" in line or "while" in line for line in lines) else "O(n)",
                "space_complexity": "O(1)",
                "confidence": "low",
                "hotspots": [],
            },
        }

    async def generate_json(self, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        _ = system_prompt
        concept = _extract_quiz_concept(user_prompt)
        return _mock_quiz_for_concept(concept)


class GroqProvider(LLMProvider):
    def __init__(
        self,
        api_key: str,
        model: str = "llama-3.3-70b-versatile",
        api_base: str = "https://api.groq.com/openai/v1",
        timeout_seconds: float = 30.0,
        max_retries: int = 2,
        retry_base_seconds: float = 1.0,
    ) -> None:
        self.api_key = api_key.strip()
        self.model = model.strip() or "llama-3.3-70b-versatile"
        self.api_base = api_base.rstrip("/")
        self.timeout_seconds = max(5.0, timeout_seconds)
        self.max_retries = max(0, max_retries)
        self.retry_base_seconds = max(0.1, retry_base_seconds)
        self.last_provider_name = "groq"
        self.last_model = self.model

    async def analyze_code(
        self, code: str, language: str = "python", context: str | None = None
    ) -> dict[str, Any]:
        system_prompt, user_prompt = _build_prompts(code=code, language=language, context=context)
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        content = await self.complete_messages(messages=messages, structured_json=True)
        return _parse_json_content(content, "Groq")

    async def generate_json(self, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        content = await self.complete_messages(messages=messages, structured_json=True)
        return _parse_json_content(content, "Groq")

    async def complete_messages(
        self,
        messages: list[dict[str, str]],
        structured_json: bool = False,
    ) -> str:
        if not messages:
            raise RuntimeError("Groq request requires at least one message.")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload: dict[str, Any] = {"model": self.model, "messages": messages}
        if structured_json:
            payload["response_format"] = {"type": "json_object"}

        errors: list[str] = []
        for attempt in range(self.max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                    response = await client.post(
                        f"{self.api_base}/chat/completions",
                        headers=headers,
                        json=payload,
                    )
            except httpx.TimeoutException as exc:
                errors.append(f"timeout: {exc}")
                if attempt >= self.max_retries:
                    break
                await asyncio.sleep(self.retry_base_seconds * (2**attempt))
                continue
            except httpx.HTTPError as exc:
                errors.append(f"network: {exc}")
                if attempt >= self.max_retries:
                    break
                await asyncio.sleep(self.retry_base_seconds * (2**attempt))
                continue

            if response.status_code == 429:
                detail = _extract_error_message(response)
                retry_after = _retry_after_seconds(response.headers)
                errors.append(f"429: {detail}")
                if attempt >= self.max_retries:
                    break
                sleep_for = retry_after if retry_after is not None else self.retry_base_seconds * (2**attempt)
                await asyncio.sleep(max(0.1, sleep_for))
                continue

            if response.status_code >= 400:
                detail = _extract_error_message(response)
                raise RuntimeError(f"Groq API error {response.status_code}: {detail}")

            body = response.json()
            choices = body.get("choices") or []
            if not choices:
                raise RuntimeError("Groq response did not include choices.")
            message = choices[0].get("message") or {}
            content = message.get("content")
            if isinstance(content, list):
                chunks = [str(part.get("text", "")) for part in content if isinstance(part, dict)]
                content = "\n".join(chunk for chunk in chunks if chunk).strip()
            if not isinstance(content, str) or not content.strip():
                raise RuntimeError("Groq response did not include textual content.")
            return content.strip()

        detail = " | ".join(errors[:5]) if errors else "unknown error"
        raise RuntimeError(f"Groq request failed after retries. Details: {detail}")


@dataclass
class ModelRateState:
    limit_requests: int | None = None
    remaining_requests: int | None = None
    reset_at: float | None = None
    blocked_until: float | None = None
    unavailable_until: float | None = None


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
        timeout_seconds: float = 15.0,
        total_timeout_seconds: float = 20.0,
        max_candidates: int = 3,
    ) -> None:
        self.api_key = api_key
        self.model = model.strip() or "auto"
        self.api_base = api_base.rstrip("/")
        self.free_only = free_only
        self.app_name = app_name
        self.site_url = site_url
        self.model_cache_seconds = max(30, model_cache_seconds)
        self.timeout_seconds = max(5.0, timeout_seconds)
        self.total_timeout_seconds = max(8.0, total_timeout_seconds)
        self.max_candidates = max(1, min(8, max_candidates))
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
        return await self._request_json_payload(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            purpose="review",
        )

    async def generate_json(self, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        return await self._request_json_payload(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            purpose="task",
        )

    async def _request_json_payload(
        self,
        system_prompt: str,
        user_prompt: str,
        purpose: str,
    ) -> dict[str, Any]:
        started_at = time.monotonic()
        needed_tokens = _estimate_tokens(system_prompt) + _estimate_tokens(user_prompt)
        candidates = await self._pick_candidate_models(needed_tokens=needed_tokens)
        if not candidates:
            raise RuntimeError("No eligible OpenRouter models are available.")
        logger.info(
            "openrouter_candidates_selected purpose=%s model_mode=%s needed_tokens=%s candidate_count=%s top_candidates=%s",
            purpose,
            self.model,
            needed_tokens,
            len(candidates),
            candidates[:3],
        )

        errors: list[str] = []
        for index, model_id in enumerate(candidates):
            fallback_attempted = index > 0
            elapsed = time.monotonic() - started_at
            remaining_budget = self.total_timeout_seconds - elapsed
            if remaining_budget <= 0:
                errors.append("total timeout budget exceeded")
                break
            attempt_timeout = max(5.0, min(self.timeout_seconds, remaining_budget))
            try:
                raw_content = await self._run_completion(
                    model_id=model_id,
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    fallback_attempted=fallback_attempted,
                    timeout_seconds=attempt_timeout,
                )
                self.last_model = model_id
                self.last_provider_name = "openrouter"
                logger.info(
                    "openrouter_json_success purpose=%s model=%s candidate_index=%s fallback_attempted=%s elapsed_seconds=%.2f",
                    purpose,
                    model_id,
                    index,
                    fallback_attempted,
                    time.monotonic() - started_at,
                )
                return _parse_json_content(raw_content, "OpenRouter")
            except _RateLimitedError as exc:
                self._mark_rate_limited(model_id=model_id, retry_after_seconds=exc.retry_after_seconds)
                logger.warning(
                    "openrouter_model_rate_limited purpose=%s model=%s candidate_index=%s retry_after_seconds=%s",
                    purpose,
                    model_id,
                    index,
                    exc.retry_after_seconds,
                )
                errors.append(f"{model_id}: {exc}")
            except _ModelHttpError as exc:
                if exc.status_code in {400, 404, 422}:
                    self._mark_model_unavailable(model_id=model_id, cooldown_seconds=900)
                elif 500 <= exc.status_code <= 599:
                    self._mark_model_unavailable(model_id=model_id, cooldown_seconds=120)
                logger.warning(
                    "openrouter_model_http_error purpose=%s model=%s candidate_index=%s status=%s error=%s",
                    purpose,
                    model_id,
                    index,
                    exc.status_code,
                    exc,
                )
                errors.append(f"{model_id}: {exc}")
            except Exception as exc:
                logger.warning(
                    "openrouter_model_failed purpose=%s model=%s candidate_index=%s fallback_attempted=%s error=%s",
                    purpose,
                    model_id,
                    index,
                    fallback_attempted,
                    exc,
                )
                errors.append(f"{model_id}: {exc}")

        raise RuntimeError(
            f"OpenRouter failed across candidate models for {purpose}. "
            f"Tried {len(candidates)} models. Details: {' | '.join(errors[:5])}"
        )

    async def _pick_candidate_models(self, needed_tokens: int) -> list[str]:
        if self.model.lower() not in {"", "auto"}:
            if self.free_only:
                lowered = self.model.lower()
                if not (lowered.endswith(":free") or lowered == "openrouter/free"):
                    try:
                        catalog = await self._get_models()
                    except Exception:
                        raise RuntimeError(
                            f"Cannot verify pricing for '{self.model}'. "
                            "Use a :free model or LLM_MODEL=auto when OPENROUTER_FREE_ONLY=true."
                        )
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
            if not _is_text_model(item):
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
            return [model_id for _, model_id in scored[: self.max_candidates]]

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
        if model_id == self.last_model:
            score += 40.0

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
        timeout_seconds: float,
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

        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
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
            raise _ModelHttpError(status_code=response.status_code, message=detail)

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

    def _mark_model_unavailable(self, model_id: str, cooldown_seconds: float) -> None:
        now = time.time()
        state = self._rate_state_by_model.get(model_id, ModelRateState())
        state.unavailable_until = now + max(30.0, cooldown_seconds)
        self._rate_state_by_model[model_id] = state
        logger.info(
            "openrouter_model_unavailable model=%s cooldown_seconds=%s until=%s",
            model_id,
            cooldown_seconds,
            state.unavailable_until,
        )


class _RateLimitedError(Exception):
    def __init__(self, message: str, retry_after_seconds: float | None) -> None:
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds


class _ModelHttpError(Exception):
    def __init__(self, status_code: int, message: str) -> None:
        self.status_code = status_code
        super().__init__(f"OpenRouter error {status_code}: {message}")


def _build_prompts(code: str, language: str, context: str | None) -> tuple[str, str]:
    system_prompt = (
        "You are an expert software reviewer. Return valid JSON only with keys: "
        "issues, summary, technical_debt, overall_assessment, refactor_suggestions, performance. "
        "Each issue must include line, type, severity (Critical/High/Medium/Low), message, suggested_fix. "
        "When possible include original_code and fixed_code snippets for each issue. "
        "Performance must include time_complexity, space_complexity, confidence, hotspots."
    )
    context_block = (context or "No repository context provided.").strip()[:3500]
    user_prompt = (
        f"Language hint: {language}\n"
        "Analyze this source code for correctness, maintainability, performance, and security.\n"
        "Validate that every issue line number exists in the source.\n"
        "Use language-specific best practices.\n"
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


def _is_text_model(item: dict[str, Any]) -> bool:
    architecture = item.get("architecture")
    if isinstance(architecture, dict):
        modality = str(architecture.get("modality", "")).lower()
        if modality:
            return "text->text" in modality
        inputs = architecture.get("input_modalities")
        outputs = architecture.get("output_modalities")
        if isinstance(inputs, list) and isinstance(outputs, list):
            return "text" in [str(v).lower() for v in inputs] and "text" in [
                str(v).lower() for v in outputs
            ]
    model_id = str(item.get("id", "")).lower()
    return "vl" not in model_id


def _model_blocked(state: ModelRateState | None, now: float) -> bool:
    if not state:
        return False
    if state.blocked_until and state.blocked_until > now:
        return True
    if state.unavailable_until and state.unavailable_until > now:
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
            code = err.get("code")
            metadata = err.get("metadata")
            provider_name: str | None = None
            provider_code: str | None = None
            if isinstance(metadata, dict):
                provider_name_value = metadata.get("provider_name")
                if provider_name_value:
                    provider_name = str(provider_name_value)
                provider_code_value = metadata.get("provider_code") or metadata.get("upstream_code")
                if provider_code_value is not None:
                    provider_code = str(provider_code_value)
            if message:
                details: list[str] = []
                if code is not None:
                    details.append(f"code={code}")
                if provider_name:
                    details.append(f"provider={provider_name}")
                if provider_code:
                    details.append(f"provider_code={provider_code}")
                if details:
                    return f"{message} ({', '.join(details)})"
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


def _validate_groq_api_key(api_key: str | None) -> str:
    key = (api_key or "").strip()
    if not key:
        raise ValueError("LLM_PROVIDER=groq requires GROQ_API_KEY.")
    return key


def _resolve_model(requested_model: str, default_model: str) -> str:
    model = (requested_model or "").strip()
    if not model:
        return default_model
    return model


def build_provider(
    provider_name: str,
    groq_api_key: str | None,
    openrouter_api_key: str | None,
    model: str,
    groq_api_base: str = "https://api.groq.com/openai/v1",
    groq_timeout_seconds: float = 30.0,
    groq_max_retries: int = 2,
    groq_retry_base_seconds: float = 1.0,
    api_base: str = "https://openrouter.ai/api/v1",
    free_only: bool = True,
    app_name: str | None = None,
    site_url: str | None = None,
    model_cache_seconds: int = 300,
    timeout_seconds: float = 15.0,
    total_timeout_seconds: float = 20.0,
    max_candidates: int = 3,
) -> LLMProvider:
    provider = (provider_name or "").strip().lower()
    groq_model = _resolve_model(model, default_model="llama-3.3-70b-versatile")
    openrouter_model = _resolve_model(model, default_model="openrouter/auto")
    if provider in {"", "auto"}:
        groq_key = (groq_api_key or "").strip()
        if groq_key:
            return GroqProvider(
                api_key=groq_key,
                model=groq_model,
                api_base=groq_api_base,
                timeout_seconds=groq_timeout_seconds,
                max_retries=groq_max_retries,
                retry_base_seconds=groq_retry_base_seconds,
            )
        key = (openrouter_api_key or "").strip()
        if key:
            return OpenRouterProvider(
                api_key=key,
                model=openrouter_model,
                api_base=api_base,
                free_only=free_only,
                app_name=app_name,
                site_url=site_url,
                model_cache_seconds=model_cache_seconds,
                timeout_seconds=timeout_seconds,
                total_timeout_seconds=total_timeout_seconds,
                max_candidates=max_candidates,
            )
        return MockProvider(model=groq_model)
    if provider == "mock":
        return MockProvider(model=groq_model)
    if provider == "groq":
        return GroqProvider(
            api_key=_validate_groq_api_key(groq_api_key),
            model=groq_model,
            api_base=groq_api_base,
            timeout_seconds=groq_timeout_seconds,
            max_retries=groq_max_retries,
            retry_base_seconds=groq_retry_base_seconds,
        )
    if provider == "openrouter":
        return OpenRouterProvider(
            api_key=_validate_openrouter_api_key(openrouter_api_key),
            model=openrouter_model,
            api_base=api_base,
            free_only=free_only,
            app_name=app_name,
            site_url=site_url,
            model_cache_seconds=model_cache_seconds,
            timeout_seconds=timeout_seconds,
            total_timeout_seconds=total_timeout_seconds,
            max_candidates=max_candidates,
        )
    raise ValueError("LLM_PROVIDER must be 'auto', 'groq', 'openrouter', or 'mock'.")


@lru_cache(maxsize=1)
def get_llm_provider() -> LLMProvider:
    return build_provider(
        provider_name=settings.LLM_PROVIDER,
        groq_api_key=settings.GROQ_API_KEY,
        openrouter_api_key=settings.OPENROUTER_API_KEY,
        model=settings.LLM_MODEL,
        groq_api_base=settings.GROQ_API_BASE,
        groq_timeout_seconds=settings.GROQ_TIMEOUT_SECONDS,
        groq_max_retries=settings.GROQ_MAX_RETRIES,
        groq_retry_base_seconds=settings.GROQ_RETRY_BASE_SECONDS,
        api_base=settings.OPENROUTER_API_BASE,
        free_only=settings.OPENROUTER_FREE_ONLY,
        app_name=settings.OPENROUTER_APP_NAME,
        site_url=settings.OPENROUTER_SITE_URL,
        model_cache_seconds=settings.OPENROUTER_MODEL_CACHE_SECONDS,
        timeout_seconds=settings.OPENROUTER_TIMEOUT_SECONDS,
        total_timeout_seconds=settings.OPENROUTER_TOTAL_TIMEOUT_SECONDS,
        max_candidates=settings.OPENROUTER_MAX_CANDIDATES,
    )


def get_provider_diagnostics() -> dict[str, Any]:
    configured = settings.LLM_PROVIDER.strip().lower()
    groq_key_present = bool((settings.GROQ_API_KEY or "").strip())
    openrouter_key_present = bool((settings.OPENROUTER_API_KEY or "").strip())
    if configured == "groq":
        provider = "groq"
    elif configured == "openrouter":
        provider = "openrouter"
    elif configured in {"", "auto"} and groq_key_present:
        provider = "groq"
    elif configured in {"", "auto"} and openrouter_key_present:
        provider = "openrouter"
    else:
        provider = "mock"
    effective = settings.effective_llm_provider
    if effective not in {"groq", "openrouter", "mock"}:
        effective = "mock"
    model_mode = (settings.LLM_MODEL or "").strip() or "auto"
    api_base = settings.GROQ_API_BASE if provider == "groq" else settings.OPENROUTER_API_BASE
    parsed = urlparse(api_base)
    api_base_host = parsed.hostname or ("api.groq.com" if provider == "groq" else "openrouter.ai")
    return {
        "provider": provider,
        "effective_provider": effective,
        "model_mode": model_mode,
        "free_only": bool(settings.OPENROUTER_FREE_ONLY) if provider == "openrouter" else False,
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


def _extract_quiz_concept(prompt: str) -> str:
    marker = "concept:"
    lowered = prompt.lower()
    if marker not in lowered:
        return "secure coding"
    idx = lowered.index(marker)
    tail = prompt[idx + len(marker) :].strip()
    if not tail:
        return "secure coding"
    first_line = tail.splitlines()[0].strip()
    return first_line[:80] or "secure coding"


def _mock_quiz_for_concept(concept: str) -> dict[str, Any]:
    topic = concept.strip() or "secure coding"
    return {
        "concept": topic,
        "questions": [
            {
                "question": f"What is the best first defense against {topic} defects?",
                "options": [
                    "Input validation and explicit allowlists",
                    "Ignoring user input edge cases",
                    "Using debug logs in production",
                    "Disabling error handling",
                ],
                "correct_option": 0,
                "explanation": "Validation and allowlists reduce exploit surface and runtime surprises.",
            },
            {
                "question": f"How should you verify fixes related to {topic}?",
                "options": [
                    "Write focused unit and integration tests",
                    "Rely on manual checks only",
                    "Skip tests after refactoring",
                    "Test only happy paths",
                ],
                "correct_option": 0,
                "explanation": "Automated tests are required to prevent regressions.",
            },
            {
                "question": "Which practice improves long-term code quality?",
                "options": [
                    "Small refactors plus code review",
                    "Patching without tests",
                    "Copy-pasting fixes",
                    "Silencing all warnings",
                ],
                "correct_option": 0,
                "explanation": "Small verified refactors keep risk low and quality high.",
            },
        ],
    }
