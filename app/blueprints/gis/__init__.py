from flask import Blueprint

gis_bp = Blueprint("gis", __name__)


@gis_bp.route("/ping", methods=["GET"])
def ping():
    """Placeholder para serviços GIS."""
    return {"service": "gis", "message": "ok"}, 200
