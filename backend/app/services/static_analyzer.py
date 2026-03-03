import ast
import re
import shlex
import shutil
import subprocess
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

from app.core.config import settings


@dataclass
class StaticIssue:
    line: int | None
    issue_type: str
    severity: str
    message: str
    suggested_fix: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "line": self.line,
            "type": self.issue_type,
            "severity": self.severity,
            "message": self.message,
            "suggested_fix": self.suggested_fix,
            "source": "static",
        }


class _LoopDepthVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.current_depth = 0
        self.max_depth = 0

    def _visit_loop(self, node: ast.AST) -> None:
        self.current_depth += 1
        self.max_depth = max(self.max_depth, self.current_depth)
        self.generic_visit(node)
        self.current_depth -= 1

    def visit_For(self, node: ast.For) -> None:
        self._visit_loop(node)

    def visit_AsyncFor(self, node: ast.AsyncFor) -> None:
        self._visit_loop(node)

    def visit_While(self, node: ast.While) -> None:
        self._visit_loop(node)


class StaticAnalyzer:
    TODO_PATTERN = re.compile(r"(#|//|/\*)\s*TODO\b", re.IGNORECASE)
    SECRET_PATTERN = re.compile(
        r"(?i)\b(api[_-]?key|secret|token|password|private[_-]?key)\b\s*[:=]\s*['\"][^'\"]{8,}['\"]"
    )
    DEBUG_LOG_PATTERNS = {
        "python": re.compile(r"\bprint\s*\(", re.IGNORECASE),
        "javascript": re.compile(r"\bconsole\.log\s*\(", re.IGNORECASE),
        "typescript": re.compile(r"\bconsole\.log\s*\(", re.IGNORECASE),
        "java": re.compile(r"\bSystem\.out\.println\s*\(", re.IGNORECASE),
    }
    JS_FUNCTION_START = re.compile(
        r"^\s*(function\s+\w+\s*\(.*\)\s*\{|(?:const|let|var)\s+\w+\s*=\s*\(?.*\)?\s*=>\s*\{)"
    )
    JAVA_METHOD_START = re.compile(
        r"^\s*(public|private|protected)?\s*(static\s+)?[\w<>\[\]]+\s+\w+\s*\(.*\)\s*\{"
    )
    JAVA_CONTROL_PREFIX = re.compile(
        r"^(if|for|while|switch|catch|try|else|do|class|interface|enum|package|import|@)\b"
    )

    def analyze(
        self, code: str, language: str = "python", filename: str | None = None
    ) -> list[dict[str, Any]]:
        normalized_language = self._resolve_language(language, filename)
        issues: list[StaticIssue] = []
        lines = code.splitlines()

        issues.extend(self._generic_line_checks(lines, normalized_language))
        issues.extend(self._find_duplicate_blocks(lines))

        if normalized_language == "python":
            issues.extend(self._python_ast_checks(code))
        elif normalized_language in {"javascript", "typescript"}:
            issues.extend(self._javascript_checks(lines, normalized_language))
        elif normalized_language == "java":
            issues.extend(self._java_checks(lines))
            issues.extend(self._run_external_java_lint(code))
        else:
            issues.extend(self._c_style_complexity_checks(lines))

        return [item.to_dict() for item in issues]

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
        return self._normalize_language(language)

    def _normalize_language(self, language: str) -> str:
        value = language.strip().lower()
        if value in {"js", "javascript"}:
            return "javascript"
        if value in {"ts", "typescript"}:
            return "typescript"
        if value in {"py", "python"}:
            return "python"
        return value

    def _generic_line_checks(self, lines: list[str], language: str) -> list[StaticIssue]:
        issues: list[StaticIssue] = []
        debug_pattern = self.DEBUG_LOG_PATTERNS.get(language)
        for idx, line in enumerate(lines, start=1):
            if self.TODO_PATTERN.search(line):
                issues.append(
                    StaticIssue(
                        line=idx,
                        issue_type="Maintainability",
                        severity="Low",
                        message="TODO comment left in code.",
                        suggested_fix="Resolve TODO or convert it to a tracked issue before release.",
                    )
                )
            if self.SECRET_PATTERN.search(line):
                issues.append(
                    StaticIssue(
                        line=idx,
                        issue_type="Security",
                        severity="High",
                        message="Potential hardcoded secret detected.",
                        suggested_fix="Load credentials from environment variables or a secrets manager.",
                    )
                )
            if debug_pattern and debug_pattern.search(line):
                issues.append(
                    StaticIssue(
                        line=idx,
                        issue_type="Maintainability",
                        severity="Low",
                        message="Debug logging statement found in source.",
                        suggested_fix="Remove or route debug logs through structured logging with levels.",
                    )
                )
        return issues

    def _python_ast_checks(self, code: str) -> list[StaticIssue]:
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return [
                StaticIssue(
                    line=1,
                    issue_type="Syntax",
                    severity="Low",
                    message="Could not parse Python source for deep static checks.",
                    suggested_fix="Fix syntax errors for a more complete static analysis pass.",
                )
            ]

        issues: list[StaticIssue] = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                issues.extend(self._function_size_check(node))
                issues.extend(self._function_complexity_check(node))
                issues.extend(self._deep_nested_loops_check(node))
                issues.extend(self._broad_exception_check(node))
            if isinstance(node, ast.ClassDef):
                issues.extend(self._god_class_check(node))
        return issues

    def _function_size_check(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[StaticIssue]:
        if not getattr(node, "end_lineno", None):
            return []
        line_count = node.end_lineno - node.lineno + 1
        if line_count <= 50:
            return []
        return [
            StaticIssue(
                line=node.lineno,
                issue_type="Maintainability",
                severity="Medium",
                message=f"Function `{node.name}` is {line_count} lines long (> 50).",
                suggested_fix="Split into smaller functions with focused responsibilities.",
            )
        ]

    def _function_complexity_check(
        self, node: ast.FunctionDef | ast.AsyncFunctionDef
    ) -> list[StaticIssue]:
        complexity = 1
        for subnode in ast.walk(node):
            if isinstance(
                subnode,
                (ast.If, ast.For, ast.While, ast.Try, ast.ExceptHandler, ast.With, ast.IfExp, ast.Match),
            ):
                complexity += 1
            if isinstance(subnode, ast.BoolOp):
                complexity += max(1, len(subnode.values) - 1)
        if complexity <= 10:
            return []
        return [
            StaticIssue(
                line=node.lineno,
                issue_type="Maintainability",
                severity="Medium",
                message=f"Function `{node.name}` has high cyclomatic complexity ({complexity}).",
                suggested_fix="Refactor branching logic into helper methods and guard clauses.",
            )
        ]

    def _deep_nested_loops_check(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[StaticIssue]:
        visitor = _LoopDepthVisitor()
        visitor.visit(node)
        if visitor.max_depth <= 2:
            return []
        return [
            StaticIssue(
                line=node.lineno,
                issue_type="Performance",
                severity="Medium",
                message=f"Deep nested loops detected (depth={visitor.max_depth}).",
                suggested_fix="Reduce nesting with indexing/precomputation or flatter control flow.",
            )
        ]

    def _broad_exception_check(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[StaticIssue]:
        for subnode in ast.walk(node):
            if isinstance(subnode, ast.ExceptHandler):
                exception = subnode.type
                if exception is None:
                    return [
                        StaticIssue(
                            line=subnode.lineno,
                            issue_type="Maintainability",
                            severity="Medium",
                            message="Bare except clause catches all exceptions.",
                            suggested_fix="Catch specific exception types and handle each case explicitly.",
                        )
                    ]
                if isinstance(exception, ast.Name) and exception.id == "Exception":
                    return [
                        StaticIssue(
                            line=subnode.lineno,
                            issue_type="Maintainability",
                            severity="Low",
                            message="Generic `except Exception` found.",
                            suggested_fix="Catch precise exceptions to avoid masking real failures.",
                        )
                    ]
        return []

    def _god_class_check(self, node: ast.ClassDef) -> list[StaticIssue]:
        method_count = sum(1 for item in node.body if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)))
        if method_count <= 15:
            return []
        return [
            StaticIssue(
                line=node.lineno,
                issue_type="Architecture",
                severity="Medium",
                message=f"Class `{node.name}` appears too large ({method_count} methods).",
                suggested_fix="Split class responsibilities into smaller focused components.",
            )
        ]

    def _javascript_checks(self, lines: list[str], language: str) -> list[StaticIssue]:
        issues: list[StaticIssue] = []
        issues.extend(self._c_style_complexity_checks(lines))
        issues.extend(self._c_style_function_size_checks(lines, self.JS_FUNCTION_START, "function"))

        async_without_try = re.compile(r"^\s*async\s+function|\s*=\s*async\s*\(", re.IGNORECASE)
        has_try = any("try {" in line for line in lines)
        if any(async_without_try.search(line) for line in lines) and not has_try:
            issues.append(
                StaticIssue(
                    line=1,
                    issue_type="Reliability",
                    severity="Low",
                    message="Async flow without obvious error handling.",
                    suggested_fix="Wrap awaited calls with try/catch and handle failures explicitly.",
                )
            )

        if language == "typescript" and any(": any" in line for line in lines):
            issues.append(
                StaticIssue(
                    line=1,
                    issue_type="Maintainability",
                    severity="Low",
                    message="TypeScript `any` usage detected.",
                    suggested_fix="Replace `any` with concrete types or validated interfaces.",
                )
            )
        return issues

    def _java_checks(self, lines: list[str]) -> list[StaticIssue]:
        issues: list[StaticIssue] = []
        issues.extend(self._c_style_complexity_checks(lines))
        issues.extend(self._c_style_function_size_checks(lines, self.JAVA_METHOD_START, "method"))
        issues.extend(self._java_regex_pitfalls(lines))
        issues.extend(self._java_syntax_sanity_checks(lines))

        synchronized_methods = [idx for idx, line in enumerate(lines, start=1) if "synchronized" in line]
        if len(synchronized_methods) > 5:
            issues.append(
                StaticIssue(
                    line=synchronized_methods[0],
                    issue_type="Performance",
                    severity="Low",
                    message="Heavy synchronized usage may reduce throughput.",
                    suggested_fix="Prefer finer-grained locking or lock-free structures when possible.",
                )
            )

        return issues

    def _java_regex_pitfalls(self, lines: list[str]) -> list[StaticIssue]:
        issues: list[StaticIssue] = []
        class_pattern = re.compile(r"\bclass\s+([A-Za-z_][A-Za-z0-9_]*)")
        pascal_case = re.compile(r"^[A-Z][A-Za-z0-9]*$")
        string_eq_pattern = re.compile(
            r'(\"[^\"]*\"\s*==\s*[A-Za-z_][A-Za-z0-9_]*|[A-Za-z_][A-Za-z0-9_]*\s*==\s*\"[^\"]*\")'
        )

        for idx, line in enumerate(lines, start=1):
            class_match = class_pattern.search(line)
            if class_match:
                class_name = class_match.group(1)
                if not pascal_case.match(class_name):
                    issues.append(
                        StaticIssue(
                            line=idx,
                            issue_type="Maintainability",
                            severity="Low",
                            message=f"Java class `{class_name}` is not PascalCase.",
                            suggested_fix="Rename class using PascalCase naming convention.",
                        )
                    )
            if string_eq_pattern.search(line):
                issues.append(
                    StaticIssue(
                        line=idx,
                        issue_type="Correctness",
                        severity="Medium",
                        message="Possible Java String comparison using `==`.",
                        suggested_fix="Use `.equals()` or `.equalsIgnoreCase()` for String comparison.",
                    )
                )
        return issues

    def _java_syntax_sanity_checks(self, lines: list[str]) -> list[StaticIssue]:
        issues: list[StaticIssue] = []
        open_braces = 0
        close_braces = 0

        for idx, line in enumerate(lines, start=1):
            stripped = line.strip()
            open_braces += stripped.count("{")
            close_braces += stripped.count("}")

            if not stripped or stripped.startswith("//") or stripped.startswith("/*") or stripped.startswith("*"):
                continue
            if stripped.endswith(("{", "}", ";", ":")):
                continue
            if self.JAVA_CONTROL_PREFIX.search(stripped):
                continue

            likely_statement = (
                "System.out." in stripped
                or "=" in stripped
                or (("(" in stripped and ")" in stripped) and not stripped.startswith("new "))
            )
            if likely_statement:
                issues.append(
                    StaticIssue(
                        line=idx,
                        issue_type="Syntax",
                        severity="High",
                        message="Possible missing semicolon in Java statement.",
                        suggested_fix="Terminate Java statements with `;`.",
                    )
                )

        if open_braces != close_braces:
            issues.append(
                StaticIssue(
                    line=1,
                    issue_type="Syntax",
                    severity="High",
                    message="Unbalanced braces detected in Java source.",
                    suggested_fix="Ensure all `{` braces have matching `}` braces.",
                )
            )

        return issues

    def _c_style_complexity_checks(self, lines: list[str]) -> list[StaticIssue]:
        loop_depth = 0
        max_depth = 0
        loop_pattern = re.compile(r"\b(for|while)\b")
        open_brace_pattern = re.compile(r"\{")
        close_brace_pattern = re.compile(r"\}")

        for line in lines:
            if loop_pattern.search(line):
                loop_depth += 1
                max_depth = max(max_depth, loop_depth)
            closes = len(close_brace_pattern.findall(line))
            if closes > 0:
                loop_depth = max(0, loop_depth - closes)
            opens = len(open_brace_pattern.findall(line))
            if opens and not loop_pattern.search(line):
                max_depth = max(max_depth, loop_depth)

        if max_depth <= 2:
            return []
        return [
            StaticIssue(
                line=1,
                issue_type="Performance",
                severity="Medium",
                message=f"Deep nested loops detected (depth={max_depth}).",
                suggested_fix="Reduce nested iteration depth using maps/indexes or pre-computed lookups.",
            )
        ]

    def _c_style_function_size_checks(
        self, lines: list[str], function_start_pattern: re.Pattern[str], label: str
    ) -> list[StaticIssue]:
        issues: list[StaticIssue] = []
        current_start: int | None = None
        brace_depth = 0

        for idx, line in enumerate(lines, start=1):
            if current_start is None and function_start_pattern.search(line):
                current_start = idx
                brace_depth = line.count("{") - line.count("}")
                continue

            if current_start is not None:
                brace_depth += line.count("{")
                brace_depth -= line.count("}")
                if brace_depth <= 0:
                    length = idx - current_start + 1
                    if length > 50:
                        issues.append(
                            StaticIssue(
                                line=current_start,
                                issue_type="Maintainability",
                                severity="Medium",
                                message=f"{label.title()} at line {current_start} is {length} lines long (> 50).",
                                suggested_fix="Break large methods into smaller cohesive units.",
                            )
                        )
                    current_start = None
        return issues

    def _run_external_java_lint(self, code: str) -> list[StaticIssue]:
        if not settings.JAVA_CHECKSTYLE_CMD and not settings.JAVA_PMD_CMD:
            return []

        with NamedTemporaryFile("w", suffix=".java", delete=False, encoding="utf-8") as tmp:
            tmp.write(code)
            tmp.flush()
            temp_file = Path(tmp.name)
        issues: list[StaticIssue] = []

        try:
            commands = [settings.JAVA_CHECKSTYLE_CMD, settings.JAVA_PMD_CMD]
            for cmd in commands:
                if not cmd:
                    continue
                parts = shlex.split(cmd)
                if not parts:
                    continue
                binary = parts[0]
                if shutil.which(binary) is None:
                    continue
                completed = subprocess.run(
                    parts + [str(temp_file)],
                    capture_output=True,
                    text=True,
                    timeout=15,
                    check=False,
                )
                if completed.returncode == 0:
                    continue
                output = completed.stdout + "\n" + completed.stderr
                snippet = output.strip().splitlines()[:3]
                if not snippet:
                    continue
                issues.append(
                    StaticIssue(
                        line=1,
                        issue_type="Maintainability",
                        severity="Low",
                        message="External Java linter reported style/design concerns.",
                        suggested_fix="Review Checkstyle/PMD output and align code with project standards.",
                    )
                )
                break
        except Exception:
            return []
        finally:
            if temp_file.exists():
                temp_file.unlink()

        return issues

    def _find_duplicate_blocks(self, lines: list[str]) -> list[StaticIssue]:
        normalized = [line.strip() for line in lines]
        window_size = 4
        seen: dict[str, int] = {}
        repeated = defaultdict(list)

        for start in range(0, len(normalized) - window_size + 1):
            block = normalized[start : start + window_size]
            if any(not row for row in block):
                continue
            signature = "\n".join(block)
            if len(signature) < 50:
                continue
            if signature in seen:
                repeated[signature].append(start + 1)
            else:
                seen[signature] = start + 1

        issues: list[StaticIssue] = []
        for signature, starts in list(repeated.items())[:4]:
            first_line = seen[signature]
            duplicate_line = starts[0]
            issues.append(
                StaticIssue(
                    line=duplicate_line,
                    issue_type="Maintainability",
                    severity="Low",
                    message=f"Duplicate code block similar to lines around {first_line}.",
                    suggested_fix="Extract duplicate logic into a reusable function/module.",
                )
            )
        return issues
