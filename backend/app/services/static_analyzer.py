import ast
import re
from collections import defaultdict
from dataclasses import dataclass
from typing import Any


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
    TODO_PATTERN = re.compile(r"#\s*TODO\b", re.IGNORECASE)
    SECRET_PATTERN = re.compile(
        r"(?i)\b(api[_-]?key|secret|token|password)\b\s*=\s*['\"][^'\"]{8,}['\"]"
    )

    def analyze(self, code: str, language: str = "python") -> list[dict[str, Any]]:
        issues: list[StaticIssue] = []
        lines = code.splitlines()

        for idx, line in enumerate(lines, start=1):
            if self.TODO_PATTERN.search(line):
                issues.append(
                    StaticIssue(
                        line=idx,
                        issue_type="Maintainability",
                        severity="Low",
                        message="TODO comment left in code.",
                        suggested_fix="Resolve or convert TODO into tracked work item.",
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

        issues.extend(self._find_duplicate_blocks(lines))

        if language.strip().lower() == "python":
            issues.extend(self._python_ast_checks(code))

        return [item.to_dict() for item in issues]

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

    def _deep_nested_loops_check(
        self, node: ast.FunctionDef | ast.AsyncFunctionDef
    ) -> list[StaticIssue]:
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
                suggested_fix="Reduce nesting via indexing, precomputation, or flatter control flow.",
            )
        ]

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
        for signature, starts in list(repeated.items())[:3]:
            first_line = seen[signature]
            duplicate_line = starts[0]
            issues.append(
                StaticIssue(
                    line=duplicate_line,
                    issue_type="Maintainability",
                    severity="Low",
                    message=f"Duplicate code block similar to lines around {first_line}.",
                    suggested_fix="Extract duplicate logic into a shared function.",
                )
            )
        return issues
