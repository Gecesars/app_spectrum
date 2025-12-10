"""
Cálculo ponto-a-ponto para interferência usando difração (P.526) com heurística de Assis.

Simplificado:
- Amostra perfil do terreno via raster (usando terrain.mean_height_along_radial);
- Usa modelo de difração por obstáculo simples (v mais alto) como aproximação;
- Integra método de Assis de forma resumida (arredondamento de topos via fator k_assis).

Retorna atenuação adicional por difração (dB) e campo resultante no ponto de recepção.
"""

import math
from typing import List, Tuple

from app.utils.propagacao.terrain import sample_height


def _parse_point_wkt(wkt: str) -> Tuple[float, float]:
    """Extrai (lat, lon) de um WKT POINT sem depender do PostGIS."""
    if not wkt:
        raise ValueError("WKT vazio")
    text = wkt.strip()
    if text.upper().startswith("SRID="):
        text = text.split(";", 1)[1]
    if not text.upper().startswith("POINT"):
        raise ValueError(f"WKT não suportado: {text}")
    coords_txt = text[text.find("(") + 1 : text.find(")")]
    parts = coords_txt.replace(",", " ").split()
    if len(parts) < 2:
        raise ValueError(f"WKT inválido: {text}")
    lon = float(parts[0])
    lat = float(parts[1])
    return lat, lon


def _distance_haversine_km(tx_lat: float, tx_lon: float, rx_lat: float, rx_lon: float) -> float:
    """Distância esférica simples, em quilômetros."""
    R = 6371.0
    dlat = math.radians(rx_lat - tx_lat)
    dlon = math.radians(rx_lon - tx_lon)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(tx_lat)) * math.cos(math.radians(rx_lat)) * math.sin(dlon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def _profile_heights(
    tx_lat: float, tx_lon: float, rx_lat: float, rx_lon: float, samples: int = 256
) -> List[Tuple[float, float]]:
    """Retorna lista de (dist_m, altura_m) do perfil entre TX e RX usando SRTM."""
    d_km = _distance_haversine_km(tx_lat, tx_lon, rx_lat, rx_lon)
    if d_km <= 0:
        return []
    profile: List[Tuple[float, float]] = []
    for idx in range(samples + 1):
        frac = idx / max(samples, 1)
        dist_m = d_km * 1000 * frac
        plat = tx_lat + (rx_lat - tx_lat) * frac
        plon = tx_lon + (rx_lon - tx_lon) * frac
        h = sample_height(plat, plon)
        if h is not None:
            profile.append((dist_m, h))
    return profile


def knife_edge_loss(v: float) -> float:
    if v <= -0.78:
        return 0.0
    return 6.9 + 20 * math.log10(math.sqrt((v - 0.1) ** 2 + 1) + v - 0.1)


def diffraction_loss(profile: List[Tuple[float, float]], freq_mhz: float, d_km: float) -> float:
    """
    Usa método de obstáculo único com maior v.
    profile: [(dist_m, altura_m)], d_km: distância total.
    """
    if not profile or d_km <= 0:
        return 0.0
    lam = 300 / freq_mhz  # metros
    k_assis = 0.5  # fator de suavização para topos arredondados (Assis)
    v_max = -99
    for dist_m, h in profile:
        d1 = dist_m
        d2 = d_km * 1000 - dist_m
        if d1 <= 0 or d2 <= 0:
            continue
        # Suponha linha de visada na altura 0 (relativa); perfil já deve ser relativo à linha de base.
        v = k_assis * (h * math.sqrt(2 / (lam * (1 / d1 + 1 / d2))))
        v_max = max(v_max, v)
    if v_max < -90:
        return 0.0
    return knife_edge_loss(v_max)


def field_strength_p2p(freq_mhz: float, erp_kw: float, tx_wkt: str, rx_wkt: str) -> float:
    """
    Campo resultante (dBµV/m) no receptor com difração.
    FSPL + ERP - L_diff
    """
    txlat, txlon = _parse_point_wkt(tx_wkt)
    rxlat, rxlon = _parse_point_wkt(rx_wkt)
    d_km = _distance_haversine_km(txlat, txlon, rxlat, rxlon)
    if d_km <= 0:
        return 0.0
    # Perfil simplificado: reusa mean_height_along_radial para uma amostra; idealmente usar raster completo.
    loss = 0.0
    try:
        profile = _profile_heights(txlat, txlon, rxlat, rxlon, samples=128)
        loss = diffraction_loss(profile, freq_mhz, d_km)
    except Exception:
        loss = 0.0

    fspl_field = 106.92 + 10 * math.log10(max(erp_kw, 0.001)) - 20 * math.log10(d_km)
    return fspl_field - loss
