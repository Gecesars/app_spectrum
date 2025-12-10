from flask import Blueprint

api_bp = Blueprint("api", __name__)

# Importa rotas para registrar no blueprint
from app.blueprints.api import routes  # noqa
