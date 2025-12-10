import sqlalchemy as sa
from celery import shared_task

from app import db
from app.models import (
    EstacaoTV,
    NormasTVDigitalClasses,
    NormasTVAnalogicaClasses,
    NormasTVNivelContorno,
    NormasTVProtecao,
    ResultadoCobertura,
    Simulacao,
)
from app.utils.propagacao.p1546_curves import field_strength_p1546
from app.utils.propagacao.terrain import destination_point, effective_height
from app.utils.propagacao.p526 import field_strength_from_erp_dbuvm, path_loss_p526_db, sample_profile


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
    Fallback: 51 dBµV/m (apenas digital).
    """
    tecnologia = "digital"

    def faixa_canal(canal: int) -> str:
        if 2 <= canal <= 6:
            return "vhf_baixo"
        if 7 <= canal <= 13:
            return "vhf_alto"
        return "uhf"

    faixa = faixa_canal(est.canal or 0)
    norma = NormasTVNivelContorno.query.filter_by(tecnologia=tecnologia, faixa_canal=faixa).first()
    if norma and norma.nivel_campo_dbuv_m:
        return norma.nivel_campo_dbuv_m
    return 51.0


def _distancia_alvo_km(est: EstacaoTV, angle: int, time_percent: float, path: str) -> float:
    """
    Distância-alvo por radial:
    - Usa dist_max_contorno_protegido_km da norma como teto, se disponível;
    - Busca distância que atinge o nível alvo via P.1546 simplificado;
    - Piso 5 km, teto 120 km.
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
            return 2 * e50 - e10  # E(50,90) derivado (aprox)
        return field_strength_p1546(
            freq_mhz=est.freq_mhz or 600.0,
            dist_km=dist_km,
            h_eff_m=_altura_efetiva(est, angle),
            time_percent=time_percent if time_percent in (50, 10, 1) else 50,
            path=path,
        )

    target = nivel_alvo
    lo, hi = 1.0, dist_cap or 120.0
    for _ in range(12):
        mid = 0.5 * (lo + hi)
        if field(mid) > target:
            lo = mid
        else:
            hi = mid
    dist = hi
    return max(5.0, dist if dist_cap is None else min(dist, dist_cap))

def _avaliar_limites_classe(est: EstacaoTV) -> tuple[bool, list[str]]:
    msgs: list[str] = []
    aprovado = True
    tecnologia = "digital"
    norma = NormasTVDigitalClasses.query.filter_by(classe=est.classe).first() if est.classe else None
    if not norma:
        msgs.append("Classe não encontrada em norma; não verificado.")
        return aprovado, msgs
    if est.erp_max_kw and est.erp_max_kw > norma.erp_max_kw:
        aprovado = False
        msgs.append(f"ERP {est.erp_max_kw} kW excede limite da classe {norma.erp_max_kw} kW.")
    if est.hnmt_m and est.hnmt_m > norma.hnmt_ref_m:
        aprovado = False
        msgs.append(f"HNMT {est.hnmt_m} m excede limite da classe {norma.hnmt_ref_m} m.")
    return aprovado, msgs


def _delta_label(delta: int) -> str:
    if delta == 0:
        return "n"
    if delta == 1:
        return "n+1"
    if delta == -1:
        return "n-1"
    if delta == 7:
        return "n+7"
    if delta == -7:
        return "n-7"
    return str(delta)


def _norma_tv(delta: int, tec_desejado: str, tec_intf: str) -> NormasTVProtecao | None:
    lbl = _delta_label(delta)
    return (
        NormasTVProtecao.query.filter_by(
            tecnologia_desejado=tec_desejado, tecnologia_interferente=tec_intf, delta_canal=lbl
        )
        .order_by(NormasTVProtecao.id)
        .first()
    )


def _avaliar_interferencias_tv(est: EstacaoTV, path: str, time_percent: float) -> tuple[bool, list[str], bool]:
    msgs: list[str] = []
    aprovado = True
    tec_des = "digital"
    nivel_alvo = _nivel_alvo_dbuv(est)
    try:
        base_wkt = db.session.scalar(sa.select(sa.func.ST_AsEWKT(est.geom)))
        base_latlon = db.session.execute(
            sa.text("SELECT ST_Y(geom) AS lat, ST_X(geom) AS lon FROM estacoes_tv WHERE id=:id"), {"id": est.id}
        ).fetchone()
        if not base_wkt or not base_latlon:
            return aprovado, msgs, False
        sql = sa.text(
            """
            SELECT id, canal, tecnologia, freq_mhz, erp_max_kw, hnmt_m,
                   ST_Y(geom) AS lat, ST_X(geom) AS lon,
                   ST_DistanceSphere(geom, ST_GeomFromText(:wkt, 4674)) / 1000.0 AS dist_km
            FROM estacoes_tv
            WHERE id != :id
              AND geom IS NOT NULL
              AND canal IS NOT NULL
              AND ST_DWithin(geom::geography, ST_GeogFromText(:wkt), 300000)
            ORDER BY dist_km
            LIMIT 100
            """
        )
        rows = db.session.execute(sql, {"id": est.id, "wkt": base_wkt}).fetchall()
        for r in rows:
            delta = (r.canal or 0) - (est.canal or 0)
            norma = _norma_tv(delta, tec_des, (r.tecnologia or "").lower())
            if not norma:
                continue
            ci_req = norma.ci_requerida_db
            try:
                profile_d, profile_h = sample_profile(r.lat, r.lon, base_latlon.lat, base_latlon.lon, samples=96)
                h_tx_asl = (profile_h[0] if profile_h else 0.0) + (r.hnmt_m or 30.0)
                h_rx_asl = (profile_h[-1] if profile_h else 0.0) + 10.0
                pl_db = path_loss_p526_db(
                    profile_d,
                    profile_h,
                    freq_mhz=r.freq_mhz or est.freq_mhz or 600.0,
                    h_tx_asl_m=h_tx_asl,
                    h_rx_asl_m=h_rx_asl,
                )
                campo_intf = field_strength_from_erp_dbuvm(r.erp_max_kw or 1.0, pl_db)
            except Exception:
                h_eff_intf = effective_height(r.lat, r.lon, 0.0, hnmt_fallback=r.hnmt_m or 30.0)
                campo_intf = field_strength_p1546(
                    freq_mhz=r.freq_mhz or est.freq_mhz or 600.0,
                    dist_km=r.dist_km or 1.0,
                    h_eff_m=h_eff_intf,
                    time_percent=time_percent if time_percent in (50, 10, 1) else 50,
                    path=path,
                )
            limite = nivel_alvo - ci_req
            if campo_intf > limite:
                aprovado = False
                msgs.append(
                    f"Interf TV: est.{r.id} Δcanal={delta} CI_req={ci_req} dB "
                    f"campo_intf={campo_intf:.1f} dBµV/m > limite {limite:.1f} dBµV/m (dist {r.dist_km:.1f} km, P.526/Assis)."
                )
        return aprovado, msgs, True
    except Exception as exc:
        db.session.rollback()
        msgs.append(f"Interferência não avaliada (erro: {str(exc)[:180]})")
        return aprovado, msgs, False


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

    angles = list(range(0, 360, 10))
    dists_km = []
    for angle in angles:
        try:
            dists_km.append(_distancia_alvo_km(est, angle, time_percent or 50, path or "Land"))
        except Exception:
            dists_km.append(10.0)

    latlon = db.session.execute(
        sa.text("SELECT ST_Y(geom) AS lat, ST_X(geom) AS lon FROM estacoes_tv WHERE id=:id"),
        {"id": est.id},
    ).fetchone()
    poly = None
    if latlon:
        coords = []
        for angle, dist_km in zip(angles, dists_km):
            plat, plon = destination_point(latlon.lat, latlon.lon, angle, dist_km * 1000.0)
            coords.append((plon, plat))
        if coords:
            coords.append(coords[0])
        if len(coords) >= 4:
            pts = ", ".join(f"{lon} {lat}" for lon, lat in coords)
            wkt = f"POLYGON(({pts}))"
            poly = sa.func.ST_GeomFromText(wkt, 4674)

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


@shared_task(name="app.tasks.tv.viabilidade")
def avaliar_viabilidade_tv(sim_id: str, estacao_id: int, time_percent: float | None = None, path: str | None = None) -> dict:
    """
    Viabilidade simplificada TV:
    - Checa limites de classe (ERP/HNMT).
    - Gera contorno protegido (P.1546 simplificado).
    - Avalia interferência básica (CI) contra demais estações TV em até 300 km.
    """
    sim = Simulacao.query.get(sim_id)
    if not sim:
        return {"status": "error", "detail": "simulação não encontrada"}

    est = EstacaoTV.query.get(estacao_id)
    if not est or not est.geom:
        sim.status = "failed"
        sim.mensagem_status = "Estação TV inválida ou sem geometria."
        db.session.commit()
        return {"status": sim.status, "detail": sim.mensagem_status}

    tp = time_percent or 50
    ph = path or "Land"

    aprovado = True
    msgs: list[str] = []

    ok_lim, msgs_lim = _avaliar_limites_classe(est)
    aprovado = aprovado and ok_lim
    msgs.extend(msgs_lim)

    inter_ok, inter_msgs, ci_eval = _avaliar_interferencias_tv(est, ph, tp)
    aprovado = aprovado and inter_ok
    msgs.extend(inter_msgs)

    angles = list(range(0, 360, 10))
    dists_km = []
    for angle in angles:
        try:
            dists_km.append(_distancia_alvo_km(est, angle, tp, ph))
        except Exception:
            dists_km.append(10.0)

    latlon = db.session.execute(
        sa.text("SELECT ST_Y(geom) AS lat, ST_X(geom) AS lon FROM estacoes_tv WHERE id=:id"),
        {"id": est.id},
    ).fetchone()
    poly_geom = None
    if latlon:
        coords = []
        for angle, dist_km in zip(angles, dists_km):
            plat, plon = destination_point(latlon.lat, latlon.lon, angle, dist_km * 1000.0)
            coords.append((plon, plat))
        if coords:
            coords.append(coords[0])
        if len(coords) >= 4:
            pts = ", ".join(f"{lon} {lat}" for lon, lat in coords)
            wkt = f"POLYGON(({pts}))"
            poly_geom = sa.func.ST_GeomFromText(wkt, 4674)

    if poly_geom is None:
        sim.status = "failed"
        sim.mensagem_status = "Falha ao gerar contorno."
        db.session.commit()
        return {"status": sim.status, "detail": sim.mensagem_status}

    contorno = ResultadoCobertura(
        simulacao_id=sim.id,
        tipo_contorno="tv_protegido_viabilidade",
        nivel_campo_dbuv_m=_nivel_alvo_dbuv(est),
        geom=poly_geom,
    )
    db.session.add(contorno)

    sim.status = "done"
    mensagem = ("Aprovado" if aprovado else "Reprovado") + (": " + "; ".join(msgs) if msgs else "")
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
