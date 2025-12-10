from flask import request, jsonify, current_app
import sqlalchemy as sa
from sqlalchemy import func

from app.blueprints.fm import fm_bp
from app.models import EstacaoFM, Simulacao
from app import db
from app.tasks.fm import gerar_contorno_fm, avaliar_viabilidade_fm
from app import make_celery
from app.utils.propagacao.p526_assis import field_strength_p2p
from app.utils.gis import geom_to_geojson


@fm_bp.route("/ping", methods=["GET"])
def ping():
    """Ping simples do módulo FM/RTR."""
    return {"service": "fm", "message": "ok"}, 200


@fm_bp.route("/estacoes", methods=["GET"])
def listar_estacoes():
    """
    Lista estações FM/RTR com filtros simples.
    Parâmetros:
      - uf: UF (ex: SP)
      - servico: FM ou RTR
      - bbox: xmin,ymin,xmax,ymax (SRID 4674)
      - limit: máximo de registros (default 100, máx 1000)
    """
    query = EstacaoFM.query
    uf = request.args.get("uf")
    servico = request.args.get("servico")
    bbox = request.args.get("bbox")
    limit = min(int(request.args.get("limit", 100)), 1000)

    if uf:
        query = query.filter(EstacaoFM.uf == uf.upper())
    if servico:
        query = query.filter(EstacaoFM.servico == servico.upper())
    if bbox:
        try:
            xmin, ymin, xmax, ymax = [float(v) for v in bbox.split(",")]
            envelope = func.ST_MakeEnvelope(xmin, ymin, xmax, ymax, 4674)
            query = query.filter(EstacaoFM.geom != None).filter(  # noqa: E711
                func.ST_Within(EstacaoFM.geom, envelope)
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
            }
        )
    return jsonify(count=len(data), results=data)


@fm_bp.route("/viabilidade", methods=["POST"])
def viabilidade_fm():
    """
    Cria simulação de viabilidade FM:
    - Checa limites de classe (ERP/HNMT).
    - Gera contorno protegido (P.1546 simplificado).
    Entrada JSON:
    {
      "estacao_id": 123
      "time_percent": 50  (opcional, 50/10/1)
      "path": "Land"|"Sea"|"Warm Sea"|"Cold Sea" (opcional, default Land)
    }
    """
    payload = request.get_json(force=True, silent=True) or {}
    estacao_id = payload.get("estacao_id")
    if not estacao_id:
        return jsonify(error="estacao_id é obrigatório"), 400

    sim = Simulacao(tipo="fm", params=payload, status="queued", mensagem_status=None)
    db.session.add(sim)
    db.session.commit()

    # Sempre enfileira no Celery; se falhar, marca erro em vez de executar inline (evita timeout no worker HTTP).
    try:
        broker = current_app.config.get("CELERY_BROKER_URL")
        current_app.logger.info(f"Enfileirando viabilidade FM no broker {broker}")
        # usa a instância global do worker, mas se algo falhar tenta instanciar Celery ad hoc.
        avaliar_viabilidade_fm.delay(sim.id, estacao_id, payload.get("time_percent"), payload.get("path"))
    except Exception as exc:
        current_app.logger.exception("Erro ao enfileirar viabilidade FM com instância padrão; tentando Celery ad hoc")
        try:
            celery = make_celery(current_app)
            celery.send_task(
                "app.tasks.fm.viabilidade",
                args=(sim.id, estacao_id, payload.get("time_percent"), payload.get("path")),
            )
        except Exception as exc2:
            sim.status = "failed"
            sim.mensagem_status = f"Falha ao enfileirar viabilidade: {exc2}"
            db.session.commit()
            return jsonify(error=sim.mensagem_status), 500

    return jsonify(id=sim.id, status=sim.status), 202


@fm_bp.route("/interferencia", methods=["POST"])
def interferencia_fm():
    """
    Calcula campo interferente ponto-a-ponto entre duas estações FM (P.526/Assis simplificado).
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

    tx = EstacaoFM.query.get(tx_id)
    rx = EstacaoFM.query.get(rx_id)
    if not tx or not rx or not tx.geom or not rx.geom:
        return jsonify(error="Estações inválidas ou sem geometria"), 400

    tx_wkt = db.session.scalar(sa.select(func.ST_AsText(tx.geom)))
    rx_wkt = db.session.scalar(sa.select(func.ST_AsText(rx.geom)))

    try:
        campo_dbuvm = field_strength_p2p(
            freq_mhz=tx.freq_mhz or 100.0,
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
