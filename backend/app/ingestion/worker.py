"""Worker de escrita em lote (Redis Streams → telemetry_raw). Lógica na etapa 4."""

import asyncio

from app.core.service import run_service


def main() -> None:
    asyncio.run(run_service("worker"))


if __name__ == "__main__":
    main()
