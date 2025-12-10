from flask import request, jsonify
from sqlalchemy import func

from app.blueprints.radcom import radcom_bp
from app.models import EstacaoRadcom, Simulacao
from app import db
from app.tasks import radcom_viabilidade
from app.utils.gis import geom_to_geojson


@radcom_bp.route("/ping", methods=["GET"])
def ping():
    """Ping simples do módulo RadCom."""
    return {"service": "radcom", "message": "ok"}, 200


@radcom_bp.route("/estacoes", methods=["GET"])
def listar_estacoes_radcom():
    """
    Lista estações RadCom.
    Parâmetros:
      - municipio (substring)
      - bbox: xmin,ymin,xmax,ymax (SRID 4674)
      - limit: padrão 100, máx 1000
    """
    query = EstacaoRadcom.query
    municipio = request.args.get("municipio")
    bbox = request.args.get("bbox")
    limit = min(int(request.args.get("limit", 100)), 1000)

    if municipio:
        like = f"%{municipio}%"
        query = query.filter(EstacaoRadcom.municipio_outorga.ilike(like))
    if bbox:
        try:
            xmin, ymin, xmax, ymax = [float(v) for v in bbox.split(",")]
            envelope = func.ST_MakeEnvelope(xmin, ymin, xmax, ymax, 4674)
            query = query.filter(EstacaoRadcom.geom != None).filter(  # noqa: E711
                func.ST_Within(EstacaoRadcom.geom, envelope)
            )
        except Exception:
            return jsonify(error="bbox inválido. Use xmin,ymin,xmax,ymax"), 400

    rows = query.limit(limit).all()
    data = []
    for est in rows:
        data.append(
            {
                "id": est.id,
                "municipio_outorga": est.municipio_outorga,
                "canal": est.canal,
                "erp_w": est.erp_w,
                "altura_sistema_m": est.altura_sistema_m,
                "geom": geom_to_geojson(est.geom),
                "area_prestacao": geom_to_geojson(est.area_prestacao),
            }
        )
    return jsonify(count=len(data), results=data)


@radcom_bp.route("/viabilidade", methods=["POST"])
def viabilidade_radcom():
    """
    Cria simulação de viabilidade RadCom.
    Entrada JSON (exemplo):
    {
        "municipio": "...",
        "coordenadas": [-47.1, -15.9],
        "erp_w": 25,
        "altura_m": 30
    }
    """
    payload = request.get_json(force=True, silent=True) or {}
    sim = Simulacao(tipo="radcom", params=payload, status="queued", mensagem_status=None)
    db.session.add(sim)
    db.session.commit()

    try:
        radcom_viabilidade.delay(sim.id, payload)
    except Exception:
        # Se o broker estiver indisponível, executa de forma síncrona para não falhar a requisição.
        radcom_viabilidade.run(sim.id, payload)

    return jsonify(id=sim.id, status=sim.status), 202
