import ast
import re
from pathlib import Path
from typing import Any


class PerformanceAnalyzer:
    PYTHON_LOOP_NODES = (ast.For, ast.AsyncFor, ast.While)
    C_STYLE_LOOP_PATTERN = re.compile(r"\b(for|while|foreach)\b", re.IGNORECASE)

    def analyze(
        self,
        code: str,
        language: str = "python",
        filename: str | None = None,
    ) -> dict[str, Any]:
        resolved = self._resolve_language(language=language, filename=filename)
        if resolved == "python":
            return self._analyze_python(code)
        return self._analyze_c_style(code)

    def _resolve_language(self, language: str, filename: str | None) -> str:
        if filename:
            suffix = Path(filename).suffix.lower()
            mapping = {
                ".py": "python",
                ".js": "javascript",
                ".jsx": "javascript",
                ".ts": "typescript",
                ".tsx": "typescript",
                ".java": "java",
            }
            if suffix in mapping:
                return mapping[suffix]
        lowered = language.strip().lower()
        if lowered in {"py", "python"}:
            return "python"
        if lowered in {"js", "javascript"}:
            return "javascript"
        if lowered in {"ts", "typescript"}:
            return "typescript"
        return lowered

    def _analyze_python(self, code: str) -> dict[str, Any]:
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return {
                "time_complexity": "Unknown",
                "space_complexity": "Unknown",
                "confidence": "low",
                "hotspots": [],
            }

        max_depth = 0
        recursion_flag = False
        hotspots: list[dict[str, Any]] = []

        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            depth = self._max_python_loop_depth(node)
            if depth > max_depth:
                max_depth = depth
            if depth >= 2:
                hotspots.append(
                    {
                        "line": node.lineno,
                        "operation": f"Nested loops in `{node.name}`",
                        "estimated_complexity": self._complexity_from_depth(depth),
                        "recommendation": "Reduce nested iteration with hashing or pre-computation.",
                        "source": "static",
                    }
                )

            recursive_calls = sum(
                1
                for sub in ast.walk(node)
                if isinstance(sub, ast.Call)
                and isinstance(sub.func, ast.Name)
                and sub.func.id == node.name
            )
            if recursive_calls >= 2:
                recursion_flag = True
                hotspots.append(
                    {
                        "line": node.lineno,
                        "operation": f"Branching recursion in `{node.name}`",
                        "estimated_complexity": "O(2^n)",
                        "recommendation": "Add memoization or switch to iterative dynamic programming.",
                        "source": "static",
                    }
                )

        if recursion_flag:
            time_complexity = "O(2^n)"
        else:
            time_complexity = self._complexity_from_depth(max_depth)

        space_complexity = "O(n)" if recursion_flag else "O(1)"
        if "append(" in code or ".add(" in code:
            space_complexity = "O(n)"

        return {
            "time_complexity": time_complexity,
            "space_complexity": space_complexity,
            "confidence": "medium",
            "hotspots": hotspots[:6],
        }

    def _analyze_c_style(self, code: str) -> dict[str, Any]:
        lines = code.splitlines()
        max_depth = 0
        loop_stack: list[int] = []
        hotspots: list[dict[str, Any]] = []

        for idx, line in enumerate(lines, start=1):
            stripped = line.strip()
            close_count = stripped.count("}")
            for _ in range(close_count):
                if loop_stack:
                    loop_stack.pop()

            if self.C_STYLE_LOOP_PATTERN.search(stripped):
                loop_stack.append(idx)
                depth = len(loop_stack)
                max_depth = max(max_depth, depth)
                if depth >= 2:
                    hotspots.append(
                        {
                            "line": idx,
                            "operation": "Nested loop region",
                            "estimated_complexity": self._complexity_from_depth(depth),
                            "recommendation": "Flatten loops or use indexed lookups/maps.",
                            "source": "static",
                        }
                    )

        time_complexity = self._complexity_from_depth(max_depth)
        space_complexity = "O(n)" if any(token in code for token in ["new ", "[]", "ArrayList", "HashMap"]) else "O(1)"
        return {
            "time_complexity": time_complexity,
            "space_complexity": space_complexity,
            "confidence": "medium",
            "hotspots": hotspots[:6],
        }

    def _max_python_loop_depth(self, node: ast.AST) -> int:
        max_depth = 0

        def walk(current: ast.AST, depth: int) -> None:
            nonlocal max_depth
            next_depth = depth + 1 if isinstance(current, self.PYTHON_LOOP_NODES) else depth
            max_depth = max(max_depth, next_depth)
            for child in ast.iter_child_nodes(current):
                walk(child, next_depth)

        walk(node, 0)
        return max_depth

    def _complexity_from_depth(self, depth: int) -> str:
        if depth <= 0:
            return "O(1)"
        if depth == 1:
            return "O(n)"
        if depth == 2:
            return "O(n^2)"
        if depth == 3:
            return "O(n^3)"
        return "O(n^k)"
