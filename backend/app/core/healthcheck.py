"""Healthcheck dos serviços de fundo: `python -m app.core.healthcheck`.

Sai com 0 se o heartbeat foi escrito há menos de 3 intervalos.
"""

import sys
from pathlib import Path

from app.core.service import heartbeat_is_fresh
from app.core.settings import get_settings


def main() -> int:
    settings = get_settings()
    fresh = heartbeat_is_fresh(
        Path(settings.heartbeat_file), settings.heartbeat_interval_seconds * 3
    )
    return 0 if fresh else 1


if __name__ == "__main__":
    sys.exit(main())
