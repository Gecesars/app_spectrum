from flask import request, jsonify, current_app
import sqlalchemy as sa
from sqlalchemy import func

from app.blueprints.tv import tv_bp
from app.models import EstacaoTV, Simulacao
from app import db
from app.tasks.tv import gerar_contorno_tv, avaliar_viabilidade_tv
from app.utils.gis import geom_to_geojson
from app.utils.propagacao.p526_assis import field_strength_p2p


@tv_bp.route("/ping", methods=["GET"])
def ping():
    """Ping simples do módulo TV/RTV."""
    return {"service": "tv", "message": "ok"}, 200


@tv_bp.route("/estacoes", methods=["GET"])
def listar_estacoes_tv():
    """
    Lista estações TV/RTV.
    Parâmetros:
      - uf
      - tecnologia (digital/analogica)
      - servico (TV/RTV/GTVD/RTVD)
      - bbox: xmin,ymin,xmax,ymax (SRID 4674)
      - limit (default 100, máx 1000)
    """
    query = EstacaoTV.query
    uf = request.args.get("uf")
    tecnologia = request.args.get("tecnologia")
    servico = request.args.get("servico")
    bbox = request.args.get("bbox")
    limit = min(int(request.args.get("limit", 100)), 1000)

    if uf:
        query = query.filter(EstacaoTV.uf == uf.upper())
    if tecnologia:
        query = query.filter(EstacaoTV.tecnologia == tecnologia.lower())
    if servico:
        query = query.filter(EstacaoTV.servico == servico.upper())
    if bbox:
        try:
            xmin, ymin, xmax, ymax = [float(v) for v in bbox.split(",")]
            envelope = func.ST_MakeEnvelope(xmin, ymin, xmax, ymax, 4674)
            query = query.filter(EstacaoTV.geom != None).filter(  # noqa: E711
                func.ST_Within(EstacaoTV.geom, envelope)
            )
        except Exception:
            return jsonify(error="bbox inválido. Use xmin,ymin,xmax,ymax"), 400

    rows = query.limit(limit).all()
    data = []
    for est in rows:
        data.append(
            {
                "id": est.id,
                "id_plano": est.id_plano,
                "servico": est.servico,
                "tecnologia": est.tecnologia,
                "canal": est.canal,
                "classe": est.classe,
                "freq_mhz": est.freq_mhz,
                "erp_kw": est.erp_max_kw,
                "hnmt_m": est.hnmt_m,
                "uf": est.uf,
                "municipio": est.municipio,
                "status": est.status,
                "entidade": est.entidade,
                "carater": est.carater,
                "categoria": est.categoria,
                "geom": geom_to_geojson(est.geom),
                "erp_por_radial": est.erp_por_radial,
                "observacoes": est.observacoes,
            }
        )
    return jsonify(count=len(data), results=data)


@tv_bp.route("/viabilidade", methods=["POST"])
def viabilidade_tv():
    """
    Cria simulação de viabilidade TV:
    - Checa limites de classe (ERP/HNMT).
    - Gera contorno protegido.
    - Avalia CI básica contra outras TV.
    Entrada JSON:
    {
      "estacao_id": 123
      "time_percent": 50 ou 10 (para analógico/digital conforme necessário)
      "path": Land/Sea/Warm Sea/Cold Sea (opcional)
    }
    """
    payload = request.get_json(force=True, silent=True) or {}
    estacao_id = payload.get("estacao_id")
    if not estacao_id:
        return jsonify(error="estacao_id é obrigatório"), 400

    sim = Simulacao(tipo="tv", params=payload, status="queued", mensagem_status=None)
    db.session.add(sim)
    db.session.commit()

    try:
        avaliar_viabilidade_tv.delay(sim.id, estacao_id, payload.get("time_percent"), payload.get("path"))
    except Exception as exc:
        sim.status = "failed"
        sim.mensagem_status = f"Falha ao enfileirar viabilidade: {exc}"
        db.session.commit()
        current_app.logger.exception("Erro ao enfileirar viabilidade TV")
        return jsonify(error=sim.mensagem_status), 500

    return jsonify(id=sim.id, status=sim.status), 202


@tv_bp.route("/interferencia", methods=["POST"])
def interferencia_tv():
    """
    Calcula campo interferente ponto-a-ponto entre duas estações TV/RTV (P.526/Assis simplificado).
    Entrada JSON:
    {
      "tx_id": 1,
      "rx_id": 2
    }
    """
    payload = request.get_json(force=True, silent=True) or {}
    tx_id = payload.get("tx_id")
    rx_id = payload.get("rx_id")
    if not tx_id or not rx_id:
        return jsonify(error="tx_id e rx_id são obrigatórios"), 400

    tx = EstacaoTV.query.get(tx_id)
    rx = EstacaoTV.query.get(rx_id)
    if not tx or not rx or not tx.geom or not rx.geom:
        return jsonify(error="Estações inválidas ou sem geometria"), 400

    tx_wkt = db.session.scalar(sa.select(func.ST_AsText(tx.geom)))
    rx_wkt = db.session.scalar(sa.select(func.ST_AsText(rx.geom)))

    try:
        campo_dbuvm = field_strength_p2p(
            freq_mhz=tx.freq_mhz or 600.0,
            erp_kw=tx.erp_max_kw or 1.0,
            tx_wkt=tx_wkt,
            rx_wkt=rx_wkt,
        )
        dist_km = db.session.scalar(sa.select(func.ST_DistanceSphere(tx.geom, rx.geom) / 1000.0))
    except Exception as exc:
        return jsonify(error=f"Erro no cálculo: {exc}"), 500

    return jsonify(
        tx_id=tx_id,
        rx_id=rx_id,
        campo_dbuv_m=campo_dbuvm,
        dist_km=dist_km,
        modelo="P.526/Assis simplificado",
    )
