"""Seed pequeno do dtc_dictionary, todo marcado "a revisar por especialista" (1.5).

Só códigos J1939 genéricos e conhecidos; descrições e severidades são ponto de partida,
não diagnóstico. A revisão está registrada como pendência em docs/progresso.md.

Revision ID: 0005_seed_dtc
Revises: 0004_telemetria
Create Date: 2026-11-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_seed_dtc"
down_revision: str | Sequence[str] | None = "0004_telemetria"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# (SPN, FMI, descrição, severidade, ação sugerida)
SEED: tuple[tuple[int, int, str, str, str], ...] = (
    (
        100,
        1,
        "Pressão do óleo do motor muito baixa",
        "critical",
        "Parar o motor com segurança e verificar o nível e a pressão do óleo.",
    ),
    (
        110,
        0,
        "Temperatura do motor muito alta",
        "critical",
        "Parar com segurança, deixar esfriar e verificar o sistema de arrefecimento.",
    ),
    (
        168,
        1,
        "Tensão da bateria muito baixa",
        "warning",
        "Verificar bateria, alternador e conexões elétricas.",
    ),
    (
        97,
        0,
        "Água no combustível detectada",
        "warning",
        "Drenar o filtro separador de água e verificar a qualidade do combustível.",
    ),
    (
        190,
        0,
        "Rotação do motor acima do normal",
        "warning",
        "Verificar a condução e o sistema de controle de rotação.",
    ),
)


def upgrade() -> None:
    for spn, fmi, description, severity, action in SEED:
        op.execute(
            sa.text(
                "INSERT INTO dtc_dictionary (spn, fmi, description_pt, severity, suggested_action) "
                "VALUES (:spn, :fmi, :d, CAST(:s AS dtc_severity), :a)"
            ).bindparams(spn=spn, fmi=fmi, d=description, s=severity, a=action)
        )


def downgrade() -> None:
    op.execute("DELETE FROM dtc_dictionary WHERE review_status = 'a_revisar_por_especialista'")
