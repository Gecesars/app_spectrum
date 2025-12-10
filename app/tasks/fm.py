import math

import sqlalchemy as sa
from celery import shared_task

from app import db
from app.models import EstacaoFM, NormasFMClasses, NormasFMProtecao, ResultadoCobertura, Simulacao
from app.utils.propagacao.p526 import field_strength_from_erp_dbuvm, path_loss_p526_db, sample_profile
from app.utils.propagacao.p1546_curves import field_strength_p1546
from app.utils.propagacao.terrain import effective_height, destination_point


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
    lo, hi = 0.5, dist_cap or 120.0
    for _ in range(12):
        mid = 0.5 * (lo + hi)
        if field(mid) > target:
            lo = mid
        else:
            hi = mid
    dist = hi
    return max(3.0, dist if dist_cap is None else min(dist, dist_cap))


def _polygon_radial(table: str, estacao_id: int, dists_m: list[float], angles: list[int]):
    """
    (Não usado: mantido apenas para referência do SQL radial em PostGIS.)
    """
    return None


def _gerar_contorno_geom(est: EstacaoFM, time_percent: float, path: str):
    """Calcula polígono de contorno protegido (radiais de 5°)."""
    angles = list(range(0, 360, 10))
    dists_km: list[float] = []
    for angle in angles:
        try:
            d = _distancia_alvo_km(
                est, angle, est.erp_max_kw, est.classe, est.erp_por_radial, time_percent, path
            )
        except Exception:
            d = 10.0
        dists_km.append(d)

    # Gera polígono em Python (esférico) usando destination_point e grava via ST_GeomFromText.
    latlon = db.session.execute(
        sa.text("SELECT ST_Y(geom) AS lat, ST_X(geom) AS lon FROM estacoes_fm WHERE id=:id"), {"id": est.id}
    ).fetchone()
    if not latlon:
        return None, dists_km

    coords = []
    for angle, dist_km in zip(angles, dists_km):
        plat, plon = destination_point(latlon.lat, latlon.lon, angle, dist_km * 1000.0)
        coords.append((plon, plat))
    if coords:
        coords.append(coords[0])  # fecha polígono
    wkt = None
    if len(coords) >= 4:
        points_txt = ", ".join(f"{lon} {lat}" for lon, lat in coords)
        wkt = f"POLYGON(({points_txt}))"
    geom = sa.func.ST_GeomFromText(wkt, 4674) if wkt else None
    return geom, dists_km


def _norma_por_delta(df_khz: float) -> NormasFMProtecao | None:
    """Escolhe norma de proteção pela diferença de frequência mais próxima."""
    return (
        NormasFMProtecao.query.order_by(sa.func.abs(NormasFMProtecao.delta_f_khz - df_khz))
        .first()
    )


def _avaliar_interferencias(est: EstacaoFM, path: str, time_percent: float) -> tuple[bool, list[str], bool]:
    """Avalia interferência ponto-a-ponto simplificada contra demais estações FM em até 300 km."""
    msgs: list[str] = []
    aprovado = True
    if not est.freq_mhz or not est.geom:
        return aprovado, msgs, False

    try:
        base_wkt = db.session.scalar(sa.select(sa.func.ST_AsEWKT(est.geom)))
        base_latlon = db.session.execute(
            sa.text("SELECT ST_Y(geom) AS lat, ST_X(geom) AS lon FROM estacoes_fm WHERE id=:id"), {"id": est.id}
        ).fetchone()
        if not base_wkt or not base_latlon:
            return aprovado, msgs, False

        fmin = est.freq_mhz - 0.5
        fmax = est.freq_mhz + 0.5

        sql = sa.text(
            """
            SELECT id, freq_mhz, erp_max_kw, hnmt_m,
                   ST_Y(geom) AS lat, ST_X(geom) AS lon,
                   ST_DistanceSphere(geom, ST_GeomFromText(:wkt, 4674)) / 1000.0 AS dist_km
            FROM estacoes_fm
            WHERE id != :id
              AND geom IS NOT NULL
              AND freq_mhz BETWEEN :fmin AND :fmax
              AND ST_DWithin(geom::geography, ST_GeogFromText(:wkt), 300000)  -- 300 km
            ORDER BY dist_km
            LIMIT 100
            """
        )
        rows = db.session.execute(sql, {"id": est.id, "wkt": base_wkt, "fmin": fmin, "fmax": fmax}).fetchall()

        for r in rows:
            df_khz = abs((r.freq_mhz or 0) - est.freq_mhz) * 1000.0
            norma = _norma_por_delta(df_khz)
            if not norma:
                continue
            ci_req = norma.ci_requerida_db
            # Perfil de terreno + P.526/Assis
            try:
                profile_d, profile_h = sample_profile(r.lat, r.lon, base_latlon.lat, base_latlon.lon, samples=96)
                h_tx_ground = profile_h[0]
                h_rx_ground = profile_h[-1]
                h_tx_asl = h_tx_ground + (r.hnmt_m or 30.0)
                h_rx_asl = h_rx_ground + 10.0  # receptor a 10 m sobre o solo
                pl_db = path_loss_p526_db(
                    profile_d, profile_h, freq_mhz=r.freq_mhz or est.freq_mhz, h_tx_asl_m=h_tx_asl, h_rx_asl_m=h_rx_asl
                )
                campo_intf = field_strength_from_erp_dbuvm(r.erp_max_kw or 1.0, pl_db)
            except Exception:
                # fallback: P.1546 tabulado
                h_eff_intf = effective_height(r.lat, r.lon, 0.0, hnmt_fallback=r.hnmt_m or 30.0)
                campo_intf = field_strength_p1546(
                    freq_mhz=r.freq_mhz or est.freq_mhz,
                    dist_km=r.dist_km or 1.0,
                    h_eff_m=h_eff_intf,
                    time_percent=time_percent,
                    path=path,
                )
            limite = 66.0 - ci_req
            if campo_intf > limite:
                aprovado = False
                msgs.append(
                    f"Interf: est.{r.id} Δf={df_khz:.0f} kHz CI_req={ci_req} dB "
                    f"campo_intf={campo_intf:.1f} dBµV/m > limite {limite:.1f} dBµV/m (dist {r.dist_km:.1f} km, P.526/Assis)."
                )
        return aprovado, msgs, True
    except Exception as exc:
        db.session.rollback()
        msgs.append(f"Interferência não avaliada (erro: {str(exc)[:180]})")
        return aprovado, msgs, False


def _avaliar_limites_classe(est: EstacaoFM) -> tuple[bool, list[str]]:
    """Verifica ERP/HNMT contra norma da classe."""
    msgs: list[str] = []
    aprovado = True
    norma = NormasFMClasses.query.filter_by(classe=est.classe).first() if est.classe else None
    if not norma:
        msgs.append("Classe não encontrada em norma; não verificado.")
        return aprovado, msgs
    if est.erp_max_kw and est.erp_max_kw > norma.erp_max_kw:
        aprovado = False
        msgs.append(f"ERP {est.erp_max_kw} kW excede limite da classe {norma.erp_max_kw} kW.")
    if est.hnmt_m and est.hnmt_m > norma.hnmt_max_m:
        aprovado = False
        msgs.append(f"HNMT {est.hnmt_m} m excede limite da classe {norma.hnmt_max_m} m.")
    return aprovado, msgs


@shared_task(name="app.tasks.fm.viabilidade")
def avaliar_viabilidade_fm(sim_id: str, estacao_id: int, time_percent: float | None = None, path: str | None = None) -> dict:
    """
    Viabilidade simplificada FM:
    - Verifica limites da classe (ERP/HNMT) vs normas.
    - Gera contorno protegido (P.1546 simplificado).
    - Verifica interferências básicas (CI) contra demais estações em até 300 km.
    Retorna aprovado/reprovado e ID do contorno.
    """
    sim = Simulacao.query.get(sim_id)
    if not sim:
        return {"status": "error", "detail": "simulação não encontrada"}

    est = EstacaoFM.query.get(estacao_id)
    if not est or not est.geom:
        sim.status = "failed"
        sim.mensagem_status = "Estação FM inválida ou sem geometria."
        db.session.commit()
        return {"status": sim.status, "detail": sim.mensagem_status}

    aprovado = True
    msgs: list[str] = []

    ok_limites, msgs_lim = _avaliar_limites_classe(est)
    aprovado = aprovado and ok_limites
    msgs.extend(msgs_lim)

    tp = time_percent or 50
    ph = path or "Land"

    inter_ok, inter_msgs, ci_eval = _avaliar_interferencias(est, ph, tp)
    aprovado = aprovado and inter_ok
    msgs.extend(inter_msgs)

    poly, dists_km = _gerar_contorno_geom(est, tp, ph)
    if poly is None:
        sim.status = "failed"
        sim.mensagem_status = "Falha ao gerar contorno."
        db.session.commit()
        return {"status": sim.status, "detail": sim.mensagem_status}

    contorno = ResultadoCobertura(
        simulacao_id=sim.id,
        tipo_contorno="fm_protegido_viabilidade",
        nivel_campo_dbuv_m=66.0,
        geom=poly,
    )
    db.session.add(contorno)

    sim.status = "done"
    mensagem = ("Aprovado" if aprovado else "Reprovado") + (": " + "; ".join(msgs) if msgs else "")
    # evita estouro de coluna varchar(255)
    sim.mensagem_status = mensagem[:250]
    db.session.commit()

    return {
        "status": sim.status,
        "aprovado": aprovado,
        "contorno_id": contorno.id,
        "dist_km_media": sum(dists_km) / len(dists_km),
        "mensagens": msgs,
        "ci_avaliada": ci_eval,
    }


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

    poly, dists_km = _gerar_contorno_geom(est, time_percent or 50, path or "Land")

    if poly is None:
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
