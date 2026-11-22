"""Cercas: polígono, círculo e linha com largura, com ponto na borda (conta como dentro)."""

import math
import uuid

import pytest

from app.adapters.geofence_shapely import ShapelyGeofenceMatcher
from app.domain.geofence import METERS_PER_DEGREE, FenceShape, Geofence, GeoPoint, bbox_for

TENANT = uuid.uuid4()
OTHER_TENANT = uuid.uuid4()
# Coordenadas fictícias no meio do oceano Atlântico Sul.
LAT0, LON0 = -30.0, -20.0


def north(lat: float, lon: float, meters: float) -> GeoPoint:
    return GeoPoint(lat + meters / METERS_PER_DEGREE, lon)


def east(lat: float, lon: float, meters: float) -> GeoPoint:
    return GeoPoint(lat, lon + meters / (METERS_PER_DEGREE * math.cos(math.radians(lat))))


def square() -> Geofence:
    ring = [[LON0, LAT0], [LON0 + 0.01, LAT0], [LON0 + 0.01, LAT0 + 0.01], [LON0, LAT0 + 0.01]]
    ring.append(ring[0])
    return Geofence(
        uuid.uuid4(), TENANT, FenceShape.POLYGON, {"type": "Polygon", "coordinates": [ring]}
    )


def circle(radius_m: float = 100.0) -> Geofence:
    return Geofence(
        uuid.uuid4(),
        TENANT,
        FenceShape.CIRCLE,
        {"type": "Point", "coordinates": [LON0, LAT0]},
        radius_m=radius_m,
    )


def line(width_m: float = 20.0) -> Geofence:
    # Eixo leste-oeste de ~1 km na latitude LAT0.
    end = east(LAT0, LON0, 1000)
    return Geofence(
        uuid.uuid4(),
        TENANT,
        FenceShape.LINE,
        {"type": "LineString", "coordinates": [[LON0, LAT0], [end.lon, end.lat]]},
        width_m=width_m,
    )


def matcher_with(*fences: Geofence) -> ShapelyGeofenceMatcher:
    m = ShapelyGeofenceMatcher()
    m.load(TENANT, fences)
    return m


class TestPoligono:
    def test_dentro_fora_e_borda(self) -> None:
        f = square()
        m = matcher_with(f)
        assert m.match(TENANT, GeoPoint(LAT0 + 0.005, LON0 + 0.005)) == [f]
        assert m.match(TENANT, GeoPoint(LAT0 + 0.02, LON0 + 0.005)) == []
        # meio da aresta sul e vértice: borda conta como dentro
        assert m.match(TENANT, GeoPoint(LAT0, LON0 + 0.005)) == [f]
        assert m.match(TENANT, GeoPoint(LAT0, LON0)) == [f]

    def test_ponto_um_metro_fora_da_aresta(self) -> None:
        f = square()
        assert matcher_with(f).match(TENANT, north(LAT0 + 0.01, LON0 + 0.005, 1.0)) == []


class TestCirculo:
    @pytest.mark.parametrize(
        ("meters", "inside"), [(0.0, True), (99.9, True), (100.0, True), (101.0, False)]
    )
    def test_distancia_ao_centro(self, meters: float, inside: bool) -> None:
        f = circle(100.0)
        m = matcher_with(f)
        assert (m.match(TENANT, north(LAT0, LON0, meters)) == [f]) is inside
        assert (m.match(TENANT, east(LAT0, LON0, meters)) == [f]) is inside


class TestLinhaComLargura:
    @pytest.mark.parametrize(
        ("offset_m", "inside"), [(0.0, True), (9.9, True), (10.0, True), (10.5, False)]
    )
    def test_distancia_ao_eixo(self, offset_m: float, inside: bool) -> None:
        f = line(width_m=20.0)  # meia largura = 10 m
        meio = east(LAT0, LON0, 500)
        p = north(meio.lat, meio.lon, offset_m)
        assert (matcher_with(f).match(TENANT, p) == [f]) is inside


class TestCacheEBbox:
    def test_bbox_inclui_raio(self) -> None:
        b = bbox_for(circle(100.0))
        assert b.max_lat - LAT0 == pytest.approx(100.0 / METERS_PER_DEGREE)
        assert b.contains(north(LAT0, LON0, 99.0))
        assert not b.contains(north(LAT0, LON0, 200.0))

    def test_varias_cercas_e_sobreposicao(self) -> None:
        c, sq = circle(100.0), square()
        hits = matcher_with(c, sq).match(TENANT, GeoPoint(LAT0, LON0))
        assert set(map(id, hits)) == {id(c), id(sq)}

    def test_cache_por_tenant_e_invalidacao(self) -> None:
        m = matcher_with(circle())
        assert m.is_loaded(TENANT)
        assert not m.is_loaded(OTHER_TENANT)
        with pytest.raises(KeyError):
            m.match(OTHER_TENANT, GeoPoint(LAT0, LON0))
        m.invalidate(TENANT)
        assert not m.is_loaded(TENANT)

    def test_cerca_de_outro_tenant_nao_entra(self) -> None:
        alheia = Geofence(
            uuid.uuid4(),
            OTHER_TENANT,
            FenceShape.CIRCLE,
            {"type": "Point", "coordinates": [LON0, LAT0]},
            radius_m=10,
        )
        with pytest.raises(ValueError, match="outro tenant"):
            ShapelyGeofenceMatcher().load(TENANT, [alheia])


@pytest.mark.parametrize(
    ("shape", "geometry", "radius", "width"),
    [
        (FenceShape.CIRCLE, {"type": "Point", "coordinates": [0, 0]}, None, None),
        (FenceShape.LINE, {"type": "LineString", "coordinates": [[0, 0], [1, 1]]}, None, None),
        (FenceShape.POLYGON, {"type": "Point", "coordinates": [0, 0]}, None, None),
        (FenceShape.CIRCLE, {"type": "Point", "coordinates": [0, 0]}, -5.0, None),
    ],
)
def test_cerca_invalida(
    shape: FenceShape, geometry: dict[str, object], radius: float | None, width: float | None
) -> None:
    with pytest.raises(ValueError):
        Geofence(uuid.uuid4(), TENANT, shape, geometry, radius_m=radius, width_m=width)
