import time
from pathlib import Path

from app.core.service import heartbeat_is_fresh, write_heartbeat


def test_heartbeat_recente_e_saudavel(tmp_path: Path) -> None:
    hb = tmp_path / "hb"
    write_heartbeat(hb)
    assert heartbeat_is_fresh(hb, 30)


def test_heartbeat_velho_ou_ausente_nao_e_saudavel(tmp_path: Path) -> None:
    hb = tmp_path / "hb"
    assert not heartbeat_is_fresh(hb, 30)
    hb.write_text(str(time.time() - 120))
    assert not heartbeat_is_fresh(hb, 30)
    hb.write_text("lixo")
    assert not heartbeat_is_fresh(hb, 30)
