"""A ingestão é extraível: não pode depender de API, KPIs, pontuação ou relatórios."""

import ast
from pathlib import Path

FORBIDDEN = ("app.api", "app.kpi", "app.scoring", "app.reports")


def test_ingestion_nao_importa_modulos_de_produto() -> None:
    root = Path(__file__).resolve().parents[1] / "app" / "ingestion"
    for file in root.rglob("*.py"):
        for node in ast.walk(ast.parse(file.read_text())):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            for n in names:
                assert not n.startswith(FORBIDDEN), f"{file.name} importa {n}"
