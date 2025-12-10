from flask import Blueprint

radcom_bp = Blueprint("radcom", __name__)

# Importa rotas
from app.blueprints.radcom import routes  # noqa: E402,F401
