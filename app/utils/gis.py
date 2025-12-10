from typing import Any, Optional

from geoalchemy2.shape import to_shape


def geom_to_geojson(geom: Any) -> Optional[dict]:
    """Converte geometria GeoAlchemy em GeoJSON simples."""
    if geom is None:
        return None
    try:
        return to_shape(geom).__geo_interface__
    except Exception:
        return None
