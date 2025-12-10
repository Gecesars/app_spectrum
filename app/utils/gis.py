from typing import Any, Dict, Optional

from geoalchemy2.shape import to_shape
from shapely.geometry import mapping


def geom_to_geojson(geom: Any) -> Optional[dict]:
    """Converte geometria GeoAlchemy em GeoJSON simples."""
    if geom is None:
        return None
    try:
        return to_shape(geom).__geo_interface__
    except Exception:
        return None


def feature_from_geom(geom: Any, properties: Dict) -> Optional[Dict]:
    """Monta Feature GeoJSON a partir de uma geometria GeoAlchemy."""
    geojson = geom_to_geojson(geom)
    if geojson is None:
        return None
    return {"type": "Feature", "geometry": geojson, "properties": properties}
