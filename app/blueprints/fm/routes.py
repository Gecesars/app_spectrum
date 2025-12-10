from flask import request, jsonify
from sqlalchemy import func

from app.blueprints.fm import fm_bp
from app.models import EstacaoFM
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
