from flask import Blueprint

fm_bp = Blueprint("fm", __name__)

# Importa rotas
from app.blueprints.fm import routes  # noqa: E402,F401
