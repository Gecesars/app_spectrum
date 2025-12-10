"""
Downloader e loader de SRTM (.hgt/.hgt.zip) para PostGIS raster.

Configurações via env (em config.py):
- SRTM_BASE_URL: base HTTP para os tiles (default USGS South America SRTM3).
- SRTM_DOWNLOAD_DIR: diretório local para armazenar tiles (default data/srtm).
- PROPAGATION_RASTER_TABLE / PROPAGATION_RASTER_COLUMN: tabela/coluna raster alvo.

Uso típico:
  python -m app.utils.etl.srtm_downloader --lat -9.7 --lon -36.6 --load
Isso baixa o tile correspondente e tenta carregar em PostGIS via raster2pgsql (se disponível no PATH).
"""

import argparse
import math
import os
import shutil
import zipfile
from contextlib import nullcontext
from pathlib import Path
from typing import Optional

import requests
import sqlalchemy as sa
from flask import current_app

from app import create_app, db


def tile_name(lat: float, lon: float) -> str:
    ns = "N" if lat >= 0 else "S"
    ew = "E" if lon >= 0 else "W"
    return f"{ns}{abs(math.floor(lat)):02d}{ew}{abs(math.floor(lon)):03d}"


def download_tile(base_url: str, download_dir: Path, name: str) -> Path:
    """
    Mapzen/Skadi estrutura: <base>/<lat_band>/<name>.hgt.gz
    Ex.: https://s3.amazonaws.com/elevation-tiles-prod/skadi/N41/N41W124.hgt.gz
    """
    download_dir.mkdir(parents=True, exist_ok=True)
    lat_band = name[:3]  # ex: N41
    url = f"{base_url.rstrip('/')}/{lat_band}/{name}.hgt.gz"
    print(f"Baixando {url} ...")
    resp = requests.get(url, stream=True, timeout=120)
    if resp.status_code != 200:
        raise RuntimeError(f"Falha ao baixar tile {name}: status {resp.status_code}")
    out_gz = download_dir / f"{name}.hgt.gz"
    with open(out_gz, "wb") as f:
        shutil.copyfileobj(resp.raw, f)
    print(f"Salvo em {out_gz}")
    # descompacta
    import gzip

    hgt_path = download_dir / f"{name}.hgt"
    with gzip.open(out_gz, "rb") as f_in, open(hgt_path, "wb") as f_out:
        shutil.copyfileobj(f_in, f_out)
    print("Descompactado.")
    return hgt_path


def load_hgt_postgis(hgt_path: Path, table: str, column: str = "rast"):
    """Carrega o arquivo .hgt para PostGIS usando ST_FromGDALRaster."""
    data = hgt_path.read_bytes()
    with db.engine.begin() as conn:
        conn.execute(
            sa.text(
                f"""
                CREATE TABLE IF NOT EXISTS {table} (
                  id serial primary key,
                  name text UNIQUE,
                  {column} raster
                );
                """
            )
        )
        conn.execute(
            sa.text(
                f"""
                INSERT INTO {table}(name, {column})
                VALUES (:name, ST_SetSRID(ST_FromGDALRaster(:data), 4326))
                ON CONFLICT (name) DO NOTHING;
                """
            ),
            {"name": hgt_path.stem, "data": data},
        )
    print(f"Carga raster concluída em {table} para {hgt_path.name}")


def ensure_tile_loaded(lat: float, lon: float, load: bool = True) -> Path:
    """Baixa tile se não existir localmente e opcionalmente carrega no PostGIS."""
    ctx = current_app if current_app else None
    cm = nullcontext() if ctx else create_app().app_context()
    with cm:
        base_url = current_app.config.get("SRTM_BASE_URL")
        download_dir = Path(current_app.config.get("SRTM_DOWNLOAD_DIR", "data/srtm"))
        table = current_app.config.get("PROPAGATION_RASTER_TABLE", "srtm_raster")
        column = current_app.config.get("PROPAGATION_RASTER_COLUMN", "rast")
        name = tile_name(lat, lon)
        hgt_path = download_dir / f"{name}.hgt"
        if not hgt_path.exists():
            hgt_path = download_tile(base_url, download_dir, name)
        if load:
            load_hgt_postgis(hgt_path, table, column)
        return hgt_path


def main(lat: float, lon: float, load: bool):
    app = create_app()
    with app.app_context():
        base_url = current_app.config.get("SRTM_BASE_URL")
        download_dir = Path(current_app.config.get("SRTM_DOWNLOAD_DIR", "data/srtm"))
        table = current_app.config.get("PROPAGATION_RASTER_TABLE", "srtm_raster")
        column = current_app.config.get("PROPAGATION_RASTER_COLUMN", "rast")
        name = tile_name(lat, lon)
        hgt = download_tile(base_url, download_dir, name)
        if load:
            raster2pgsql_load(hgt, table, column)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Baixa tile SRTM e (opcionalmente) carrega em PostGIS.")
    parser.add_argument("--lat", type=float, required=True, help="latitude (decimal)")
    parser.add_argument("--lon", type=float, required=True, help="longitude (decimal)")
    parser.add_argument("--load", action="store_true", help="carregar em PostGIS usando raster2pgsql + psql")
    args = parser.parse_args()
    main(args.lat, args.lon, args.load)
