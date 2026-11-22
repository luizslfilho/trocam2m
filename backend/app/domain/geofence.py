"""Cercas (geofences): tipos, bbox e a interface `GeofenceMatcher`.

Sem PostGIS na v1: a geometria fica em GeoJSON (`jsonb`) e o teste ponto-em-cerca roda em
Python atrás de `GeofenceMatcher`. Trocar por PostGIS depois não mexe nas regras.

Tipos de cerca (os mesmos da Wialon):
- `polygon`: GeoJSON `Polygon`;
- `circle`: GeoJSON `Point` (centro) + `radius_m`;
- `line`: GeoJSON `LineString` + `width_m` (largura TOTAL da faixa; o ponto está dentro se
  estiver a no máximo `width_m / 2` do eixo). TODO(doc): confirmar na documentação da
  Wialon se a largura é total ou de cada lado antes do conector (etapa 5).

Coordenadas GeoJSON são `[lon, lat]`. Ponto exatamente na borda conta como dentro.
"""

import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Protocol
from uuid import UUID

# Metros por grau de latitude (esfera de raio médio 6.371.008,8 m).
METERS_PER_DEGREE = 6_371_008.8 * math.pi / 180


class FenceShape(StrEnum):
    POLYGON = "polygon"
    CIRCLE = "circle"
    LINE = "line"


_GEOJSON_TYPE = {
    FenceShape.POLYGON: "Polygon",
    FenceShape.CIRCLE: "Point",
    FenceShape.LINE: "LineString",
}


@dataclass(frozen=True, slots=True)
class GeoPoint:
    lat: float
    lon: float


@dataclass(frozen=True, slots=True)
class BBox:
    min_lat: float
    min_lon: float
    max_lat: float
    max_lon: float

    def contains(self, p: GeoPoint) -> bool:
        return self.min_lat <= p.lat <= self.max_lat and self.min_lon <= p.lon <= self.max_lon


@dataclass(frozen=True, slots=True)
class Geofence:
    id: UUID
    tenant_id: UUID
    shape: FenceShape
    geometry: Mapping[str, Any]
    radius_m: float | None = None
    width_m: float | None = None
    allowed_idle: bool = False
    speed_limit_kmh: float | None = None

    def __post_init__(self) -> None:
        expected = _GEOJSON_TYPE[self.shape]
        if self.geometry.get("type") != expected:
            raise ValueError(f"cerca {self.shape} exige GeoJSON {expected}")
        if (self.shape is FenceShape.CIRCLE) != (self.radius_m is not None):
            raise ValueError("radius_m só existe (e é obrigatório) em cerca circular")
        if (self.shape is FenceShape.LINE) != (self.width_m is not None):
            raise ValueError("width_m só existe (e é obrigatório) em cerca de linha")
        if self.radius_m is not None and self.radius_m <= 0:
            raise ValueError("radius_m precisa ser positivo")
        if self.width_m is not None and self.width_m <= 0:
            raise ValueError("width_m precisa ser positivo")

    @property
    def margin_m(self) -> float:
        """Distância máxima do traçado que ainda conta como dentro."""
        if self.radius_m is not None:
            return self.radius_m
        if self.width_m is not None:
            return self.width_m / 2
        return 0.0


def _coordinates(fence: Geofence) -> list[tuple[float, float]]:
    coords: Any = fence.geometry["coordinates"]
    if fence.shape is FenceShape.CIRCLE:
        return [(float(coords[0]), float(coords[1]))]
    if fence.shape is FenceShape.LINE:
        return [(float(c[0]), float(c[1])) for c in coords]
    return [(float(c[0]), float(c[1])) for ring in coords for c in ring]


def bbox_for(fence: Geofence) -> BBox:
    """Retângulo que contém a cerca inteira, já com raio/meia largura. Usado como pré-filtro."""
    pts = _coordinates(fence)
    lons = [p[0] for p in pts]
    lats = [p[1] for p in pts]
    margin = fence.margin_m
    dlat = margin / METERS_PER_DEGREE
    worst_lat = min(89.0, max(abs(min(lats)), abs(max(lats))) + dlat)
    dlon = margin / (METERS_PER_DEGREE * math.cos(math.radians(worst_lat)))
    return BBox(
        min_lat=min(lats) - dlat,
        min_lon=min(lons) - dlon,
        max_lat=max(lats) + dlat,
        max_lon=max(lons) + dlon,
    )


class GeofenceMatcher(Protocol):
    """Diz em quais cercas de um tenant um ponto está. Implementações guardam cache por tenant."""

    def load(self, tenant_id: UUID, fences: Iterable[Geofence]) -> None: ...

    def is_loaded(self, tenant_id: UUID) -> bool: ...

    def invalidate(self, tenant_id: UUID) -> None: ...

    def match(self, tenant_id: UUID, point: GeoPoint) -> Sequence[Geofence]: ...
