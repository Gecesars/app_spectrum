"""
Modelo simplificado da Recomendação ITU-R P.526 (difração) com ajuste Assis.

Implementa:
- Perfil de terreno amostrado ao longo do enlace.
- Perca de espaço livre + maior perda por obstáculo do tipo knife-edge.
- Ajuste opcional de curvatura (método Assis simplificado) como perda extra.

Aviso: este é um modelo de primeira ordem para uso interno. Para cálculos
regulatórios completos, substituir por implementação certificada da P.526/Assis.
"""

from __future__ import annotations

import math
from typing import List, Tuple

from app.utils.propagacao.terrain import destination_point, sample_height


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distância esférica aproximada em metros."""
    R = 6371000.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def initial_bearing_deg(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Azimute inicial da geodésica (graus)."""
    dlon = math.radians(lon2 - lon1)
    lat1r = math.radians(lat1)
    lat2r = math.radians(lat2)
    x = math.sin(dlon) * math.cos(lat2r)
    y = math.cos(lat1r) * math.sin(lat2r) - math.sin(lat1r) * math.cos(lat2r) * math.cos(dlon)
    brg = math.degrees(math.atan2(x, y))
    return (brg + 360) % 360


def sample_profile(lat1: float, lon1: float, lat2: float, lon2: float, samples: int = 128) -> Tuple[List[float], List[float]]:
    """
    Amostra perfil de terreno ao longo do enlace.
    Retorna (distâncias_m, alturas_asl_m). Sempre inclui origem (0 m) e destino.
    Alturas faltantes são preenchidas com 0 para manter o comprimento da lista.
    """
    total_m = haversine_m(lat1, lon1, lat2, lon2)
    if total_m <= 1.0:
        h0 = sample_height(lat1, lon1) or 0.0
        return [0.0, total_m], [h0, h0]

    bearing = initial_bearing_deg(lat1, lon1, lat2, lon2)
    dists: List[float] = []
    heights: List[float] = []
    for i in range(samples):
        frac = i / max(samples - 1, 1)
        dist = total_m * frac
        plat, plon = destination_point(lat1, lon1, bearing, dist)
        h = sample_height(plat, plon)
        dists.append(dist)
        heights.append(h if h is not None else 0.0)
    return dists, heights


def knife_edge_loss_db(freq_mhz: float, d1_m: float, d2_m: float, h_diff_m: float) -> float:
    """
    Perda por difração (knife-edge) para um obstáculo com altura h_diff acima da LOS.
    Fórmula ITU/Lee: v = h * sqrt(2*(d1+d2)/(lambda*d1*d2)), L = 6.9 + 20log(sqrt((v-0.1)^2+1)+v-0.1)
    """
    if h_diff_m <= 0:
        return 0.0
    lamb = 300.0 / freq_mhz  # metros
    v = h_diff_m * math.sqrt(2.0 * (d1_m + d2_m) / (lamb * d1_m * d2_m))
    if v <= -0.78:
        return 0.0
    return 6.9 + 20.0 * math.log10(math.sqrt((v - 0.1) ** 2 + 1) + v - 0.1)


def assis_extra_loss_db(distances_m: List[float], heights_m: List[float]) -> float:
    """
    Ajuste simples inspirado no método Assis: calcula curvatura média do perfil.
    Se a curvatura for elevada (perfil convexo), adiciona perda extra limitada.
    """
    if len(distances_m) < 3 or len(heights_m) < 3:
        return 0.0
    slopes = []
    for i in range(1, len(distances_m)):
        dd = distances_m[i] - distances_m[i - 1]
        if dd <= 0:
            continue
        slopes.append((heights_m[i] - heights_m[i - 1]) / dd)
    if len(slopes) < 2:
        return 0.0
    curvatures = []
    for i in range(1, len(slopes)):
        curvatures.append(slopes[i] - slopes[i - 1])
    if not curvatures:
        return 0.0
    rms_curv = math.sqrt(sum(c * c for c in curvatures) / len(curvatures))
    # fator empírico limitado a 10 dB para evitar exageros
    return min(10.0, rms_curv * 0.001 * 1000.0)  # escala suave (aprox. dB)


def path_loss_p526_db(
    distances_m: List[float],
    heights_m: List[float],
    freq_mhz: float,
    h_tx_asl_m: float,
    h_rx_asl_m: float,
    apply_assis: bool = True,
) -> float:
    """
    Calcula perda total (dB) = FSPL + difração máxima + ajuste Assis (opcional).
    """
    if not distances_m or not heights_m or len(distances_m) != len(heights_m):
        raise ValueError("Perfil inválido para P.526")
    d_tot_km = distances_m[-1] / 1000.0
    if d_tot_km <= 0:
        return 0.0
    # Espaço livre (distância total)
    fspl = 32.45 + 20.0 * math.log10(freq_mhz) + 20.0 * math.log10(d_tot_km)

    # Maior obstáculo acima da LOS
    max_loss = 0.0
    total_m = distances_m[-1]
    for d, h in zip(distances_m[1:-1], heights_m[1:-1]):
        h_los = h_tx_asl_m + (h_rx_asl_m - h_tx_asl_m) * (d / total_m)
        h_diff = h - h_los
        if h_diff <= 0:
            continue
        loss = knife_edge_loss_db(freq_mhz, d, total_m - d, h_diff)
        if loss > max_loss:
            max_loss = loss

    loss_assis = assis_extra_loss_db(distances_m, heights_m) if apply_assis else 0.0
    return fspl + max_loss + loss_assis


def field_strength_from_erp_dbuvm(erp_kw: float, path_loss_db: float) -> float:
    """
    Converte ERP (kW) e perda total (dB) em campo elétrico (dBµV/m).
    Fórmula padrão: E = 106.92 + 10*log10(ERP_kW) - L.
    """
    erp_kw = max(erp_kw, 0.001)
    return 106.92 + 10.0 * math.log10(erp_kw) - path_loss_db
