import json

import pytest

from app.core.logging import REDACTED, configure_logging, get_logger


def test_log_nao_registra_dados_pessoais(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging("INFO", "teste")
    get_logger("t").info(
        "evento",
        asset_id="a-1",
        placa="ABC1D23",
        driver_name="Motorista Fictício",
        payload={"lat": -23.5, "lon": -46.6, "speed": 50, "nested": [{"RFID": "00AB"}]},
        **{"X-Ingest-Token": "segredo"},
    )
    line = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert line["asset_id"] == "a-1"
    assert line["service"] == "teste"
    assert line["placa"] == REDACTED
    assert line["driver_name"] == REDACTED
    assert line["X-Ingest-Token"] == REDACTED
    assert line["payload"]["lat"] == REDACTED
    assert line["payload"]["lon"] == REDACTED
    assert line["payload"]["speed"] == 50
    assert line["payload"]["nested"][0]["RFID"] == REDACTED
