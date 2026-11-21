"""Laço base dos serviços de fundo (worker, poller, scheduler).

Na etapa 1 só mantêm um heartbeat em arquivo, usado pelo healthcheck do container.
A lógica de cada serviço chega nas etapas 4, 5 e 11.
"""

import asyncio
import contextlib
import signal
import time
from pathlib import Path

from app.core.logging import configure_logging, get_logger
from app.core.settings import get_settings


def write_heartbeat(path: Path) -> None:
    path.write_text(str(time.time()))


def heartbeat_is_fresh(path: Path, max_age_seconds: float) -> bool:
    try:
        last = float(path.read_text())
    except (OSError, ValueError):
        return False
    return (time.time() - last) <= max_age_seconds


async def run_service(name: str) -> None:
    settings = get_settings()
    configure_logging(settings.log_level, name)
    log = get_logger(name)
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)

    heartbeat = Path(settings.heartbeat_file)
    log.info("service_started")
    while not stop.is_set():
        write_heartbeat(heartbeat)
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(stop.wait(), timeout=settings.heartbeat_interval_seconds)
    log.info("service_stopped")
