from typing import Any

from app.services.llm_provider import LLMProvider, get_llm_provider


class LearningService:
    def __init__(self, provider: LLMProvider | None = None) -> None:
        self.provider = provider or get_llm_provider()

    def infer_concept(self, issues: list[dict[str, Any]]) -> str:
        if not issues:
            return "Secure Coding Fundamentals"
        text = " ".join(
            f"{item.get('type', '')} {item.get('message', '')}".lower()
            for item in issues
            if isinstance(item, dict)
        )
        if "sql injection" in text or "dynamic sql" in text:
            return "SQL Injection Prevention"
        if "ssrf" in text:
            return "SSRF Mitigation"
        if "deserialization" in text:
            return "Insecure Deserialization"
        if "eval" in text or "code execution" in text:
            return "Unsafe Dynamic Execution"
        if "secret" in text or "api key" in text or "token" in text:
            return "Secret Management"
        if "complexity" in text or "nested loop" in text:
            return "Algorithmic Complexity"
        return "Secure Coding Fundamentals"

    async def generate_quiz(self, concept: str) -> dict[str, Any]:
        normalized_concept = concept.strip() or "Secure Coding Fundamentals"
        system_prompt = (
            "You are a software engineering instructor. Return strict JSON with keys: "
            "concept, questions. questions must be an array of exactly 3 items. "
            "Each item must have question, options (exactly 4 strings), correct_option (0..3), explanation."
        )
        user_prompt = (
            f"Concept: {normalized_concept}\n"
            "Generate practical multiple-choice quiz questions for developers. "
            "Questions should test reasoning, not memorization."
        )
        try:
            payload = await self.provider.generate_json(system_prompt=system_prompt, user_prompt=user_prompt)
            return self._normalize_quiz(payload, fallback_concept=normalized_concept, source="ai")
        except Exception:
            return self._normalize_quiz({}, fallback_concept=normalized_concept, source="mock")

    def _normalize_quiz(
        self,
        payload: dict[str, Any],
        fallback_concept: str,
        source: str,
    ) -> dict[str, Any]:
        concept = str(payload.get("concept", fallback_concept)).strip() or fallback_concept
        raw_questions = payload.get("questions", [])
        if not isinstance(raw_questions, list):
            raw_questions = []

        questions: list[dict[str, Any]] = []
        for item in raw_questions:
            if not isinstance(item, dict):
                continue
            options = item.get("options", [])
            if not isinstance(options, list):
                continue
            clean_options = [str(option) for option in options if str(option).strip()]
            if len(clean_options) != 4:
                continue
            try:
                correct_option = int(item.get("correct_option", 0))
            except (TypeError, ValueError):
                correct_option = 0
            if correct_option < 0 or correct_option > 3:
                correct_option = 0
            questions.append(
                {
                    "question": str(item.get("question", "Choose the most secure option.")),
                    "options": clean_options,
                    "correct_option": correct_option,
                    "explanation": str(item.get("explanation", "This option best reduces risk.")),
                }
            )

        if len(questions) < 3:
            questions = self._fallback_questions(concept)

        return {
            "concept": concept,
            "source": source,
            "questions": questions[:3],
        }

    def _fallback_questions(self, concept: str) -> list[dict[str, Any]]:
        return [
            {
                "question": f"What is the strongest first control for {concept}?",
                "options": [
                    "Strict input validation and allowlists",
                    "Suppressing errors and warnings",
                    "Running code with admin privileges",
                    "Skipping code reviews on small changes",
                ],
                "correct_option": 0,
                "explanation": "Validation and allowlists limit attack surface and malformed states.",
            },
            {
                "question": "How do you verify a security fix is stable?",
                "options": [
                    "Add automated tests and negative test cases",
                    "Rely only on local manual testing",
                    "Deploy and monitor without tests",
                    "Ignore edge cases to reduce complexity",
                ],
                "correct_option": 0,
                "explanation": "Automated tests prevent regressions and document expected behavior.",
            },
            {
                "question": "What review practice improves long-term maintainability?",
                "options": [
                    "Small, test-backed refactors and peer reviews",
                    "Large one-shot rewrites without tests",
                    "Copying code to avoid abstraction",
                    "Disabling static analysis warnings",
                ],
                "correct_option": 0,
                "explanation": "Incremental verified changes lower risk and improve readability.",
            },
        ]
