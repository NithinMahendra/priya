from pathlib import Path

from app.core.config import BACKEND_DIR, PROJECT_ROOT, settings

IGNORE_DIRS = {".git", ".venv", "__pycache__", "node_modules", "dist", "build"}


class ProjectContextBuilder:
    def build(self, user_context: str | None = None) -> str:
        parts: list[str] = []
        if user_context:
            parts.append("User Context:\n" + user_context.strip())

        readme_text = self._read_readme_excerpt()
        if readme_text:
            parts.append("README Excerpt:\n" + readme_text)

        project_tree = self._collect_project_tree()
        if project_tree:
            parts.append("Project Structure Snapshot:\n" + project_tree)

        context = "\n\n".join(parts).strip()
        return context[: settings.PROJECT_CONTEXT_MAX_CHARS]

    def _read_readme_excerpt(self) -> str:
        candidates = [
            PROJECT_ROOT / "README.md",
            BACKEND_DIR / "README.md",
        ]
        for file_path in candidates:
            if file_path.exists():
                return file_path.read_text(encoding="utf-8", errors="ignore")[:2500]
        return ""

    def _collect_project_tree(self) -> str:
        root = PROJECT_ROOT
        if not root.exists():
            return ""

        lines: list[str] = []
        max_items = 60
        for path in sorted(root.rglob("*")):
            if len(lines) >= max_items:
                break
            if any(segment in IGNORE_DIRS for segment in path.parts):
                continue
            relative = path.relative_to(root)
            depth = len(relative.parts)
            if depth > 3:
                continue
            if path.is_file():
                lines.append(str(relative).replace("\\", "/"))
        return "\n".join(lines)
