"""Poller das plataformas (Wialon pull; RedGPS em TODO(doc)). Lógica na etapa 5."""

import asyncio

from app.core.service import run_service


def main() -> None:
    asyncio.run(run_service("poller"))


if __name__ == "__main__":
    main()
