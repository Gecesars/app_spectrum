from flask import Blueprint

rtr_bp = Blueprint("rtr", __name__)


@rtr_bp.route("/ping", methods=["GET"])
def ping():
    """Placeholder para módulo RTR específico."""
    return {"service": "rtr", "message": "ok"}, 200
