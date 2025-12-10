from flask import request, jsonify
from sqlalchemy import func

from app.blueprints.tv import tv_bp
from app.models import EstacaoTV
from app.utils.gis import geom_to_geojson


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
