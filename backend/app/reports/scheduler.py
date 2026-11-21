"""Agendador de relatórios e tarefas periódicas. Lógica na etapa 11."""

import asyncio

from app.core.service import run_service


def main() -> None:
    asyncio.run(run_service("scheduler"))


if __name__ == "__main__":
    main()
