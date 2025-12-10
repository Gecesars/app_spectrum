from flask import Blueprint

radcom_bp = Blueprint("radcom", __name__)


@radcom_bp.route("/ping", methods=["GET"])
def ping():
    """Placeholder para módulo RadCom."""
    return {"service": "radcom", "message": "ok"}, 200
