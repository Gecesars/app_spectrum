import math

import sqlalchemy as sa
from celery import shared_task

from app import db
from app.models import EstacaoFM, NormasFMClasses, ResultadoCobertura, Simulacao
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


def _altura_efetiva(est: EstacaoFM, angle: float) -> float:
    """
    Altura efetiva: tenta calcular via raster ao longo do radial; fallback usa hnmt_m ou 30 m.
    """
    try:
        if est.geom is not None:
            latlon = db.session.execute(
                sa.text("SELECT ST_Y(geom) AS lat, ST_X(geom) AS lon FROM estacoes_fm WHERE id=:id"),
                {"id": est.id},
            ).fetchone()
            if latlon and latlon.lat is not None and latlon.lon is not None:
                return effective_height(latlon.lat, latlon.lon, angle, hnmt_fallback=est.hnmt_m or 30.0)
    except Exception:
        pass
    return est.hnmt_m or 30.0


def _distancia_alvo_km(
    est: EstacaoFM,
    angle: int,
    erp_kw: float | None,
    classe: str | None,
    erp_por_radial: list[float] | None,
    time_percent: float,
    path: str,
) -> float:
    """
    Define distância-alvo do contorno protegido, radial por radial:
    - Usa dist_max_contorno66_km da norma como teto base se existir;
    - Busca distância onde campo ≈ 66 dBµV/m com P.1546 simplificado;
    - Piso 3 km, teto 200 km.
    """
    erp_base = erp_kw or 1.0
    erp_eff = _erp_kw_por_radial(erp_base, erp_por_radial, angle)

    dist_cap = None
    if classe:
        norma = NormasFMClasses.query.filter_by(classe=classe).first()
        if norma and norma.dist_max_contorno66_km:
            dist_cap = norma.dist_max_contorno66_km

    def field(dist_km: float) -> float:
        return field_strength_p1546(
            freq_mhz=est.freq_mhz or 100.0,
            dist_km=dist_km,
            h_eff_m=_altura_efetiva(est, angle),
            time_percent=time_percent,
            path=path,
        )

    target = 66.0
    lo, hi = 0.5, dist_cap or 200.0
    for _ in range(40):
        mid = 0.5 * (lo + hi)
        if field(mid) > target:
            lo = mid
        else:
            hi = mid
    dist = hi
    return max(3.0, dist if dist_cap is None else min(dist, dist_cap))


def _polygon_radial(table: str, estacao_id: int, dists_m: list[float], angles: list[int]):
    """
    Gera polígono a partir de radiais via PostGIS ST_Project em geografia.
    Recebe listas alinhadas de distâncias (metros) e ângulos (graus).
    """
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


@shared_task(name="app.tasks.fm.contorno")
def gerar_contorno_fm(sim_id: str, estacao_id: int, time_percent: float | None = None, path: str | None = None) -> dict:
    """Gera contorno protegido FM simplificado (polígono radial) e grava em resultados_cobertura."""
    sim = Simulacao.query.get(sim_id)
    if not sim:
        return {"status": "error", "detail": "simulação não encontrada"}

    est = EstacaoFM.query.get(estacao_id)
    if not est or not est.geom:
        sim.status = "failed"
        sim.mensagem_status = "Estação FM inválida ou sem geometria."
        db.session.commit()
        return {"status": sim.status, "detail": sim.mensagem_status}

    angles = list(range(0, 360, 5))
    dists_km = [
        _distancia_alvo_km(
            est, angle, est.erp_max_kw, est.classe, est.erp_por_radial, time_percent or 50, path or "Land"
        )
        for angle in angles
    ]
    dists_m = [d * 1000 for d in dists_km]

    poly = _polygon_radial("estacoes_fm", estacao_id, dists_m, angles)

    if not poly:
        sim.status = "failed"
        sim.mensagem_status = "Falha ao gerar contorno."
        db.session.commit()
        return {"status": sim.status, "detail": sim.mensagem_status}

    contorno = ResultadoCobertura(
        simulacao_id=sim.id,
        tipo_contorno="fm_protegido_stub",
        nivel_campo_dbuv_m=66.0,
        geom=poly,
    )
    db.session.add(contorno)
    sim.status = "done"
    sim.mensagem_status = "Contorno FM gerado (radiais 5°, P.1546 simplificado)."
    db.session.commit()

    return {"status": sim.status, "contorno_id": contorno.id, "dist_km_media": sum(dists_km) / len(dists_km)}
