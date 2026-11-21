"""Logs estruturados em JSON. Nunca registram dados pessoais (LGPD, Seção 4).

Campos com nomes sensíveis são trocados por "[removido]" antes de sair, em qualquer nível
de aninhamento. A lista é conservadora: na dúvida, o campo sai.
"""

import logging
import sys
from collections.abc import Mapping, MutableMapping
from typing import Any

import structlog

REDACTED = "[removido]"

SENSITIVE_KEYS = frozenset(
    {
        "name",
        "nome",
        "driver_name",
        "full_name",
        "email",
        "e_mail",
        "phone",
        "telefone",
        "cpf",
        "cnh",
        "document",
        "documento",
        "plate",
        "placa",
        "imei",
        "vin",
        "rfid",
        "ibutton",
        "lat",
        "lon",
        "lng",
        "latitude",
        "longitude",
        "position",
        "posicao",
        "address",
        "endereco",
        "password",
        "senha",
        "token",
        "access_token",
        "refresh_token",
        "authorization",
        "cookie",
        "secret",
        "api_key",
        "x_ingest_token",
    }
)


def _normalize(key: str) -> str:
    return key.lower().replace("-", "_")


def _scrub(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            k: (REDACTED if _normalize(str(k)) in SENSITIVE_KEYS else _scrub(v))
            for k, v in value.items()
        }
    if isinstance(value, list | tuple):
        return [_scrub(v) for v in value]
    return value


def redact_personal_data(
    _logger: Any, _method: str, event_dict: MutableMapping[str, Any]
) -> MutableMapping[str, Any]:
    for key in list(event_dict):
        if _normalize(key) in SENSITIVE_KEYS:
            event_dict[key] = REDACTED
        else:
            event_dict[key] = _scrub(event_dict[key])
    return event_dict


def configure_logging(level: str = "INFO", service: str = "api") -> None:
    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=level)
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            redact_personal_data,
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.getLevelName(level)),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=False,
    )
    structlog.contextvars.bind_contextvars(service=service)


def get_logger(name: str | None = None) -> Any:
    return structlog.get_logger(name)
