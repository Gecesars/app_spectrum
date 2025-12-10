from flask import jsonify
from shapely.geometry import mapping

from app.blueprints.api import api_bp


@api_bp.route("/health", methods=["GET"])
def health() -> tuple:
    """Endpoint simples para verificar saúde da aplicação."""
    return jsonify(status="ok"), 200


@api_bp.route("/simulacoes/<sim_id>/status", methods=["GET"])
def simulacao_status(sim_id: str):
    """Retorna status e mensagem de uma simulação."""
    from app.models import Simulacao  # import tardio para evitar ciclos
    sim = Simulacao.query.get(sim_id)
    if not sim:
        return jsonify(error="simulação não encontrada"), 404
    return (
        jsonify(
            id=sim.id,
            tipo=sim.tipo,
            status=sim.status,
            mensagem_status=sim.mensagem_status,
            params=sim.params,
            created_at=sim.created_at,
            updated_at=sim.updated_at,
        ),
        200,
    )


@api_bp.route("/simulacoes/<sim_id>/contornos", methods=["GET"])
def simulacao_contornos(sim_id: str):
    """Retorna FeatureCollection GeoJSON dos contornos de uma simulação."""
    from app.models import Simulacao, ResultadoCobertura  # late import
    from app.utils.gis import geom_to_geojson

    sim = Simulacao.query.get(sim_id)
    if not sim:
        return jsonify(error="simulação não encontrada"), 404

    results = (
        ResultadoCobertura.query.filter_by(simulacao_id=sim_id)
        .order_by(ResultadoCobertura.id)
        .all()
    )
    features = []
    for r in results:
        gj = geom_to_geojson(r.geom)
        if not gj:
            continue
        features.append(
            {
                "type": "Feature",
                "geometry": gj,
                "properties": {
                    "id": r.id,
                    "simulacao_id": sim_id,
                    "tipo_contorno": r.tipo_contorno,
                    "nivel_campo_dbuv_m": r.nivel_campo_dbuv_m,
                },
            }
        )
    return jsonify({"type": "FeatureCollection", "features": features})


@api_bp.route("/contornos/<int:contorno_id>", methods=["GET"])
def contorno_geojson(contorno_id: int):
    """Retorna um contorno específico (Feature GeoJSON)."""
    from app.models import ResultadoCobertura  # late import
    from app.utils.gis import feature_from_geom

    r = ResultadoCobertura.query.get(contorno_id)
    if not r:
        return jsonify(error="contorno não encontrado"), 404
    feat = feature_from_geom(
        r.geom,
        {
            "id": r.id,
            "simulacao_id": r.simulacao_id,
            "tipo_contorno": r.tipo_contorno,
            "nivel_campo_dbuv_m": r.nivel_campo_dbuv_m,
        },
    )
    if not feat:
        return jsonify(error="geometria ausente"), 404
    return jsonify(feat)
