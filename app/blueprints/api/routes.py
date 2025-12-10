from flask import jsonify
from shapely.geometry import mapping

from app.blueprints.api import api_bp
from app import db
import sqlalchemy as sa


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


@api_bp.route("/contornos/<int:contorno_id>/stats", methods=["GET"])
def contorno_stats(contorno_id: int):
    """
    Retorna área (km²) e população estimada pela interseção com setores censitários.
    População ponderada pela fração de área do setor sobreposta ao contorno (pop_total pode ser nula).
    """
    from app.models import ResultadoCobertura  # late import

    contorno = ResultadoCobertura.query.get(contorno_id)
    if not contorno or not contorno.geom:
        return jsonify(error="contorno não encontrado ou sem geometria"), 404

    poly_wkt = db.session.scalar(sa.select(sa.func.ST_AsEWKT(contorno.geom)))
    if not poly_wkt:
        return jsonify(error="geometria inválida"), 404

    sql = sa.text(
        """
        WITH poly AS (SELECT ST_GeomFromText(:poly, 4674) AS g),
        setores AS (
          SELECT
            s.id,
            s.pop_total,
            ST_Area(s.geom::geography)/1e6 AS area_setor_km2,
            ST_Area(ST_Intersection(s.geom, p.g)::geography)/1e6 AS area_int_km2
          FROM setores_censitarios s
          CROSS JOIN poly p
          WHERE ST_Intersects(s.geom, p.g)
        )
        SELECT
          COALESCE(SUM(area_int_km2),0) AS area_km2,
          SUM(CASE WHEN pop_total IS NULL THEN NULL
                   WHEN area_setor_km2 > 0 THEN pop_total * (area_int_km2 / area_setor_km2)
                   ELSE NULL END) AS pop_estimada,
          COUNT(*) AS setores_intersect
        FROM setores
        WHERE area_int_km2 > 0;
        """
    )
    row = db.session.execute(sql, {"poly": poly_wkt}).fetchone()
    return jsonify(
        contorno_id=contorno_id,
        area_km2=float(row.area_km2) if row and row.area_km2 is not None else 0.0,
        pop_estimada=float(row.pop_estimada) if row and row.pop_estimada is not None else None,
        setores_intersect=int(row.setores_intersect) if row and row.setores_intersect is not None else 0,
    )
