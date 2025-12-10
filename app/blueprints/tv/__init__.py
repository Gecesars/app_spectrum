from flask import Blueprint

tv_bp = Blueprint("tv", __name__)

# Importa rotas
from app.blueprints.tv import routes  # noqa: E402,F401
