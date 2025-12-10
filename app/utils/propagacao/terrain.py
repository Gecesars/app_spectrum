"""
Amostragem de terreno a partir de tiles SRTM (.hgt) baixados localmente.
Dependências: numpy; downloader `ensure_tile_loaded` para garantir o arquivo.
"""

import math
from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np
import sqlalchemy as sa

from flask import current_app

from app import db
from app.utils.etl.srtm_downloader import ensure_tile_loaded

EARTH_RADIUS_M = 6371000.0


def _hgt_path(lat: float, lon: float) -> Path:
    return Path(ensure_tile_loaded(lat, lon, load=False, download=False))


def _read_hgt(path: Path) -> np.ndarray:
    data = np.fromfile(path, np.dtype(">i2"))
    if data.size != 1201 * 1201:
        raise ValueError(f"Tamanho inesperado em {path}")
    return data.reshape((1201, 1201))


def _height_from_db(lat: float, lon: float) -> Optional[float]:
    """Tenta obter altura via raster no PostGIS (tabela configurada)."""
    try:
        cfg = current_app.config if current_app else {}
        table = cfg.get("PROPAGATION_RASTER_TABLE", "srtm_raster")
        column = cfg.get("PROPAGATION_RASTER_COLUMN", "rast")
        sql = sa.text(
            f"""
            SELECT ST_Value({column}, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)) AS h
            FROM {table}
            WHERE ST_Intersects({column}, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326))
            LIMIT 1;
            """
        )
        row = db.session.execute(sql, {"lat": lat, "lon": lon}).fetchone()
        if row and row.h is not None:
            return float(row.h)
    except Exception:
        return None
    return None


def sample_height(lat: float, lon: float) -> Optional[float]:
    """Retorna altura do terreno (m) via SRTM; None se não conseguir."""
    # 1) tenta PostGIS raster
    h_db = _height_from_db(lat, lon)
    if h_db is not None:
        return h_db
    # 2) fallback arquivo .hgt local
    try:
        path = _hgt_path(lat, lon)
        if not path.exists():
            return None
        arr = _read_hgt(path)
        lat_floor = math.floor(lat)  # SW corner latitude
        lon_floor = math.floor(lon)  # SW corner longitude
        # índice linha: 0 no norte, 1200 no sul
        row = int(round((lat_floor + 1 - lat) * 1200))
        # índice coluna: 0 no oeste, 1200 no leste
        col = int(round((lon - lon_floor) * 1200))
        row = max(0, min(1200, row))
        col = max(0, min(1200, col))
        val = arr[row, col]
        if val == -32768:
            return None
        return float(val)
    except Exception:
        return None


def destination_point(lat: float, lon: float, bearing_deg: float, distance_m: float) -> Tuple[float, float]:
    """Calcula ponto destino a partir de lat/lon inicial, azimute e distância (esférica)."""
    brad = math.radians(bearing_deg)
    lat1 = math.radians(lat)
    lon1 = math.radians(lon)
    ang_dist = distance_m / EARTH_RADIUS_M
    lat2 = math.asin(
        math.sin(lat1) * math.cos(ang_dist) + math.cos(lat1) * math.sin(ang_dist) * math.cos(brad)
    )
    lon2 = lon1 + math.atan2(
        math.sin(brad) * math.sin(ang_dist) * math.cos(lat1),
        math.cos(ang_dist) - math.sin(lat1) * math.sin(lat2),
    )
    return math.degrees(lat2), math.degrees(lon2)


def mean_height_along_radial(
    lat: float,
    lon: float,
    angle_deg: float,
    dist_start_m: float = 3000.0,
    dist_end_m: float = 15000.0,
    samples: int = 20,
) -> float:
    """Média de alturas ao longo de um radial usando SRTM; falha se nenhuma amostra válida."""
    heights: List[float] = []
    for idx in range(samples):
        dist = dist_start_m + (dist_end_m - dist_start_m) * idx / max(samples - 1, 1)
        plat, plon = destination_point(lat, lon, angle_deg, dist)
        h = sample_height(plat, plon)
        if h is not None:
            heights.append(h)
    if not heights:
        raise RuntimeError("Nenhuma amostra de terreno válida no radial (SRTM).")
    return float(np.mean(heights))


def effective_height(lat: float, lon: float, angle_deg: float, hnmt_fallback: float = 30.0) -> float:
    """
    Altura efetiva: altura da estação - média do terreno em 3-15 km no radial.
    Lê altitude do terreno no ponto como sample_height.
    """
    try:
        h0 = sample_height(lat, lon)
        if h0 is None:
            raise RuntimeError("Altura no ponto da estação indisponível (SRTM).")
        h_mean = mean_height_along_radial(lat, lon, angle_deg, dist_start_m=3000, dist_end_m=15000, samples=20)
        h_eff = h0 - h_mean
        return h_eff if h_eff > 0 else hnmt_fallback
    except Exception:
        # Fallback para HNMT fornecida ou padrão quando não houver raster disponível.
        return hnmt_fallback
