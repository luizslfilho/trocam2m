"""`GeofenceMatcher` com shapely: pré-filtro por bbox e cache das cercas por tenant.

Cada cerca é projetada num plano local em metros (equirretangular centrado na própria
cerca). Para cercas de até dezenas de km o erro é desprezível frente à precisão do GPS.
"""

import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Any
from uuid import UUID

import shapely
from shapely.geometry import LineString, Point, Polygon, shape

from app.domain.geofence import (
    METERS_PER_DEGREE,
    BBox,
    FenceShape,
    Geofence,
    GeoPoint,
    bbox_for,
)

# Tolerância numérica da borda: ponto a até 1 cm do traçado conta como na borda (dentro).
BORDER_TOLERANCE_M = 0.01


@dataclass(frozen=True, slots=True)
class _Prepared:
    fence: Geofence
    bbox: BBox
    geom: Any
    tolerance_m: float
    lat0: float
    lon0: float
    cos_lat0: float

    def project(self, lon: float, lat: float) -> tuple[float, float]:
        return (
            (lon - self.lon0) * self.cos_lat0 * METERS_PER_DEGREE,
            (lat - self.lat0) * METERS_PER_DEGREE,
        )


def _prepare(fence: Geofence) -> _Prepared:
    exact = bbox_for(fence)
    lat0 = (exact.min_lat + exact.max_lat) / 2
    lon0 = (exact.min_lon + exact.max_lon) / 2
    cos_lat0 = math.cos(math.radians(lat0))
    # Folga da tolerância de borda no pré-filtro, para não cortar ponto exatamente na borda.
    pad_lat = BORDER_TOLERANCE_M / METERS_PER_DEGREE
    pad_lon = pad_lat / cos_lat0
    bbox = BBox(
        exact.min_lat - pad_lat,
        exact.min_lon - pad_lon,
        exact.max_lat + pad_lat,
        exact.max_lon + pad_lon,
    )

    def proj(c: Any) -> tuple[float, float]:
        return (
            (float(c[0]) - lon0) * cos_lat0 * METERS_PER_DEGREE,
            (float(c[1]) - lat0) * METERS_PER_DEGREE,
        )

    raw = shape(fence.geometry)
    geom: Any
    if fence.shape is FenceShape.CIRCLE:
        geom = Point(proj(raw.coords[0]))
    elif fence.shape is FenceShape.LINE:
        geom = LineString([proj(c) for c in raw.coords])
    else:
        geom = Polygon(
            [proj(c) for c in raw.exterior.coords],
            [[proj(c) for c in ring.coords] for ring in raw.interiors],
        )
        if not geom.is_valid:
            raise ValueError(f"polígono inválido na cerca {fence.id}")
    shapely.prepare(geom)
    return _Prepared(
        fence=fence,
        bbox=bbox,
        geom=geom,
        tolerance_m=fence.margin_m + BORDER_TOLERANCE_M,
        lat0=lat0,
        lon0=lon0,
        cos_lat0=cos_lat0,
    )


class ShapelyGeofenceMatcher:
    def __init__(self) -> None:
        self._cache: dict[UUID, list[_Prepared]] = {}

    def load(self, tenant_id: UUID, fences: Iterable[Geofence]) -> None:
        prepared = []
        for fence in fences:
            if fence.tenant_id != tenant_id:
                raise ValueError("cerca de outro tenant não entra no cache deste tenant")
            prepared.append(_prepare(fence))
        self._cache[tenant_id] = prepared

    def is_loaded(self, tenant_id: UUID) -> bool:
        return tenant_id in self._cache

    def invalidate(self, tenant_id: UUID) -> None:
        self._cache.pop(tenant_id, None)

    def match(self, tenant_id: UUID, point: GeoPoint) -> Sequence[Geofence]:
        if tenant_id not in self._cache:
            raise KeyError("cercas do tenant não carregadas; chame load() antes")
        hits: list[Geofence] = []
        for p in self._cache[tenant_id]:
            if not p.bbox.contains(point):
                continue
            pt = Point(p.project(point.lon, point.lat))
            if shapely.dwithin(p.geom, pt, p.tolerance_m):
                hits.append(p.fence)
        return hits
