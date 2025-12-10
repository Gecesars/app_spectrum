from flask import jsonify

from app.blueprints.api import api_bp


@api_bp.route("/health", methods=["GET"])
def health() -> tuple:
    """Endpoint simples para verificar saúde da aplicação."""
    return jsonify(status="ok"), 200
