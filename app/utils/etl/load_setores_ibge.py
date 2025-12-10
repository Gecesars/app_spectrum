import json
import os
from typing import List

import shapefile  # pyshp
import sqlalchemy as sa

from app import create_app, db


def load_setores(shp_path: str, batch_size: int = 500) -> None:
    if not os.path.exists(shp_path):
        raise FileNotFoundError(f"Shapefile não encontrado: {shp_path}")

    insert_sql = sa.text(
        """
        INSERT INTO setores_censitarios (id, municipio, tipo, pop_total, geom)
        VALUES (:id, :municipio, :tipo, NULL, ST_SetSRID(ST_GeomFromGeoJSON(:geom), 4674))
        ON CONFLICT (id) DO NOTHING
        """
    )

    # Limpa tabela antes de carregar
    db.session.execute(sa.text("TRUNCATE TABLE setores_censitarios RESTART IDENTITY CASCADE"))
    db.session.commit()

    reader = shapefile.Reader(shp_path)
    total = reader.numRecords
    print(f"Carregando {total} setores de {shp_path} ...")

    params_batch: List[dict] = []
    error_count = 0

    for idx, (rec, shp) in enumerate(zip(reader.iterRecords(), reader.iterShapes()), start=1):
        attrs = rec.as_dict()
        geom_geojson = shp.__geo_interface__
        if not geom_geojson or not geom_geojson.get("coordinates"):
            error_count += 1
            continue

        params_batch.append(
            {
                "id": attrs.get("CD_SETOR"),
                "municipio": attrs.get("NM_MUN"),
                "tipo": (attrs.get("SITUACAO") or "").lower(),
                "geom": json.dumps(geom_geojson),
            }
        )

        if len(params_batch) >= batch_size:
            db.session.execute(insert_sql, params_batch)
            db.session.commit()
            params_batch.clear()
            if idx % 5000 == 0:
                print(f"{idx} registros carregados...")

    if params_batch:
        db.session.execute(insert_sql, params_batch)
        db.session.commit()

    print(f"Carga de setores concluída. Erros de geometria: {error_count}")


def run() -> None:
    shp_path = os.path.join("data", "BR_setores_CD2022.shp")
    load_setores(shp_path)


if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        run()
