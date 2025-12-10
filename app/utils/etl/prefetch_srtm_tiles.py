"""
Pré-download de tiles SRTM (.hgt) para todas as estações FM/TV com geometria.

Uso:
  python -m app.utils.etl.prefetch_srtm_tiles            # baixa apenas
  python -m app.utils.etl.prefetch_srtm_tiles --load     # baixa e tenta carregar no PostGIS
"""

import argparse
from typing import Iterable, Set, Tuple, Optional

import sqlalchemy as sa

from app import create_app, db
from app.utils.etl.srtm_downloader import ensure_tile_loaded, tile_name


def _collect_coords(table: str, uf: Optional[str] = None) -> Iterable[Tuple[float, float]]:
    sql = f"SELECT ST_Y(geom) AS lat, ST_X(geom) AS lon FROM {table} WHERE geom IS NOT NULL"
    params = {}
    if uf:
        sql += " AND uf = :uf"
        params["uf"] = uf.upper()
    for row in db.session.execute(sa.text(sql), params):
        yield float(row.lat), float(row.lon)


def prefetch(load: bool = False, uf: Optional[str] = None) -> Set[str]:
    tiles: Set[str] = set()
    # Coleta FM e TV (radcom não é prioridade para terrenos altos)
    for lat, lon in _collect_coords("estacoes_fm", uf):
        tiles.add(tile_name(lat, lon))
    for lat, lon in _collect_coords("estacoes_tv", uf):
        tiles.add(tile_name(lat, lon))

    for name in sorted(tiles):
        # Usa o centro aproximado do tile para evitar bordas
        lat = int(name[1:3]) * (1 if name[0] == "N" else -1) + 0.5
        lon = int(name[4:7]) * (1 if name[3] == "E" else -1) + 0.5
        print(f"Baixando {name} (load={'on' if load else 'off'})...")
        ensure_tile_loaded(lat, lon, load=load)
    print(f"Total de tiles processados: {len(tiles)}")
    return tiles


def main(load: bool = False):
    app = create_app()
    with app.app_context():
        prefetch(load=load, uf=args.uf if 'args' in globals() else None)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Pré-baixa tiles SRTM para as estações FM/TV.")
    parser.add_argument("--load", action="store_true", help="carregar também no PostGIS (raster)")
    parser.add_argument("--uf", type=str, help="filtrar estações por UF para limitar downloads")
    args = parser.parse_args()
    main(load=args.load)
