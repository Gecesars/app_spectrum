import math

import sqlalchemy as sa
from celery import shared_task

from app import db
from app.models import (
    EstacaoTV,
    NormasTVDigitalClasses,
    NormasTVAnalogicaClasses,
    ResultadoCobertura,
    Simulacao,
)
from app.utils.propagacao.p1546_curves import field_strength_p1546
from app.utils.propagacao.terrain import effective_height


def _erp_kw_por_radial(erp_kw: float, erp_por_radial: list[float] | None, angle: int) -> float:
    """Ajusta ERP por radial se o diagrama estiver disponível (valores presumidos em dBd)."""
    if not erp_por_radial or len(erp_por_radial) != 72:
        return erp_kw
    idx = angle // 5
    ganho_db = erp_por_radial[idx] or 0.0
    fator = 10 ** (ganho_db / 10.0)
    return max(0.001, erp_kw * fator)


def _altura_efetiva(est: EstacaoTV, angle: float) -> float:
    """Altura efetiva por radial: tenta raster; fallback hnmt ou 30 m."""
    try:
        if est.geom is not None:
            latlon = db.session.execute(
                sa.text("SELECT ST_Y(geom) AS lat, ST_X(geom) AS lon FROM estacoes_tv WHERE id=:id"),
                {"id": est.id},
            ).fetchone()
            if latlon and latlon.lat is not None and latlon.lon is not None:
                return effective_height(latlon.lat, latlon.lon, angle, hnmt_fallback=est.hnmt_m or 30.0)
    except Exception:
        pass
    return est.hnmt_m or 30.0


def _nivel_alvo_dbuv(est: EstacaoTV) -> float:
    """
    Recupera nível de contorno protegido para TV conforme faixa/tecnologia.
    Fallbacks:
      - digital: 51 dBµV/m
      - analógica: 64 dBµV/m
    """
    tecnologia = (est.tecnologia or "").lower()

    def faixa_canal(canal: int) -> str:
        if 2 <= canal <= 6:
            return "vhf_baixo"
        if 7 <= canal <= 13:
            return "vhf_alto"
        return "uhf"

    faixa = faixa_canal(est.canal or 0)
    from app.models import NormasTVNivelContorno

    norma = (
        NormasTVNivelContorno.query.filter_by(tecnologia=tecnologia, faixa_canal=faixa).first()
    )
    if norma and norma.nivel_campo_dbuv_m:
        return norma.nivel_campo_dbuv_m
    return 51.0 if tecnologia == "digital" else 64.0


def _distancia_alvo_km(est: EstacaoTV, angle: int, time_percent: float, path: str) -> float:
    """
    Distância-alvo por radial:
    - Usa dist_max_contorno_protegido_km da norma como teto, se disponível;
    - Busca distância que atinge o nível alvo via P.1546 simplificado;
    - Piso 5 km, teto 200 km.
    """
    tecnologia = (est.tecnologia or "").lower()
    erp_base = est.erp_max_kw or 1.0
    erp_eff = _erp_kw_por_radial(erp_base, est.erp_por_radial, angle)

    dist_cap = None
    if est.classe:
        if tecnologia == "digital":
            norma = NormasTVDigitalClasses.query.filter_by(classe=est.classe).first()
        else:
            norma = NormasTVAnalogicaClasses.query.filter_by(classe=est.classe).first()
        if norma and norma.dist_max_contorno_protegido_km:
            dist_cap = norma.dist_max_contorno_protegido_km

    nivel_alvo = _nivel_alvo_dbuv(est)
    def field(dist_km: float) -> float:
        if tecnologia == "digital":
            e50 = field_strength_p1546(
                freq_mhz=est.freq_mhz or 600.0,
                dist_km=dist_km,
                h_eff_m=_altura_efetiva(est, angle),
                time_percent=time_percent if time_percent in (50, 10, 1) else 50,
                path=path,
            )
            e10 = field_strength_p1546(
                freq_mhz=est.freq_mhz or 600.0,
                dist_km=dist_km,
                h_eff_m=_altura_efetiva(est, angle),
                time_percent=10,
                path=path,
            )
            return 2 * e50 - e10  # E(50,90) derivado
        return field_strength_p1546(
            freq_mhz=est.freq_mhz or 600.0,
            dist_km=dist_km,
            h_eff_m=_altura_efetiva(est, angle),
            time_percent=time_percent if time_percent in (50, 10, 1) else 50,
            path=path,
        )

    target = nivel_alvo
    lo, hi = 1.0, dist_cap or 200.0
    for _ in range(40):
        mid = 0.5 * (lo + hi)
        if field(mid) > target:
            lo = mid
        else:
            hi = mid
    dist = hi
    return max(5.0, dist if dist_cap is None else min(dist, dist_cap))


def _polygon_radial(table: str, estacao_id: int, dists_m: list[float], angles: list[int]):
    sql = sa.text(
        f"""
        WITH base AS (SELECT geom::geography AS g FROM {table} WHERE id = :id),
        params AS (
            SELECT unnest(:angles)::float AS angle, unnest(:dists)::float AS dist_m
        ),
        radiais AS (
          SELECT
            angle,
            ST_Project(base.g, params.dist_m, radians(angle))::geometry(POINT, 4674) AS pt
          FROM base, params
          ORDER BY angle
        )
        SELECT ST_MakePolygon(
                 ST_AddPoint(
                   ST_MakeLine(ARRAY(SELECT pt FROM radiais ORDER BY angle)),
                   (SELECT pt FROM radiais ORDER BY angle LIMIT 1)
                 )
               ) AS geom;
        """
    )
    row = db.session.execute(sql, {"angles": angles, "dists": dists_m, "id": estacao_id}).fetchone()
    return row.geom if row else None


@shared_task(name="app.tasks.tv.contorno")
def gerar_contorno_tv(sim_id: str, estacao_id: int, time_percent: float | None = None, path: str | None = None) -> dict:
    """Gera contorno protegido TV/RTV simplificado (polígono radial)."""
    sim = Simulacao.query.get(sim_id)
    if not sim:
        return {"status": "error", "detail": "simulação não encontrada"}

    est = EstacaoTV.query.get(estacao_id)
    if not est or not est.geom:
        sim.status = "failed"
        sim.mensagem_status = "Estação TV inválida ou sem geometria."
        db.session.commit()
        return {"status": sim.status, "detail": sim.mensagem_status}

    angles = list(range(0, 360, 5))
    dists_km = [
        _distancia_alvo_km(est, angle, time_percent or 50, path or "Land") for angle in angles
    ]
    dists_m = [d * 1000 for d in dists_km]

    poly = _polygon_radial("estacoes_tv", estacao_id, dists_m, angles)

    if not poly:
        sim.status = "failed"
        sim.mensagem_status = "Falha ao gerar contorno."
        db.session.commit()
        return {"status": sim.status, "detail": sim.mensagem_status}

    contorno = ResultadoCobertura(
        simulacao_id=sim.id,
        tipo_contorno="tv_protegido_stub",
        nivel_campo_dbuv_m=_nivel_alvo_dbuv(est),
        geom=poly,
    )
    db.session.add(contorno)
    sim.status = "done"
    sim.mensagem_status = "Contorno TV gerado (radiais 5°, P.1546 simplificado)."
    db.session.commit()

    return {"status": sim.status, "contorno_id": contorno.id, "dist_km_media": sum(dists_km) / len(dists_km)}
