"""app/rules has no database or framework imports."""

import ast
from pathlib import Path

FORBIDDEN = ("sqlalchemy", "fastapi", "starlette", "psycopg", "pydantic", "app.db", "app.models", "app.config")


def test_rules_import_nothing_from_the_database_or_framework():
    for path in Path("app/rules").glob("*.py"):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            for n in names:
                assert not n.startswith(FORBIDDEN), f"{path} imports {n}"
