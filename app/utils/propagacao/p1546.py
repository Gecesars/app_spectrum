import math
from typing import Optional


def campo_p1546_simplificado(
    freq_mhz: float,
    erp_kw: float,
    dist_km: float,
    h_eff_m: Optional[float] = None,
) -> float:
    """
    Estimativa simplificada de intensidade de campo (dBµV/m) usando FSPL + ERP.
    Não substitui P.1546, mas serve como placeholder até integrar curvas oficiais.

    E(dBµV/m) ≈ 106.92 + 10*log10(ERP[kW]) - 20*log10(d[km]) + k(h_eff)
    Onde k(h_eff) é um ajuste simples: +10*log10(h_eff/10) se altura efetiva for conhecida.
    """
    if dist_km <= 0:
        dist_km = 0.1
    erp_kw = max(erp_kw, 0.001)
    k_h = 0.0
    if h_eff_m and h_eff_m > 0:
        k_h = 10 * math.log10(h_eff_m / 10.0)
    return 106.92 + 10 * math.log10(erp_kw) - 20 * math.log10(dist_km) + k_h


def distancia_para_nivel(
    freq_mhz: float,
    erp_kw: float,
    nivel_alvo_dbuv_m: float,
    dist_min_km: float = 0.5,
    dist_max_km: float = 200.0,
    max_iter: int = 30,
    h_eff_m: Optional[float] = None,
) -> float:
    """
    Busca binária para achar a distância onde o campo cai para o nível alvo.
    Usa a função simplificada de campo; destina-se apenas a gerar um contorno aproximado.
    """
    lo = dist_min_km
    hi = dist_max_km
    for _ in range(max_iter):
        mid = 0.5 * (lo + hi)
        campo_mid = campo_p1546_simplificado(freq_mhz, erp_kw, mid, h_eff_m)
        if campo_mid > nivel_alvo_dbuv_m:
            lo = mid
        else:
            hi = mid
    return hi
