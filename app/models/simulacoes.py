import uuid
from datetime import datetime

from geoalchemy2 import Geometry
from sqlalchemy.dialects.postgresql import JSONB

from app import db


def default_uuid() -> str:
    return str(uuid.uuid4())


class Simulacao(db.Model):
    __tablename__ = "simulacoes"

    id = db.Column(db.String(36), primary_key=True, default=default_uuid)
    tipo = db.Column(db.String(32), nullable=False)  # fm, radcom, tv_digital, tv_analogica, etc.
    params = db.Column(db.JSON().with_variant(JSONB, "postgresql"), nullable=True)
    status = db.Column(db.String(16), nullable=False, default="queued")
    mensagem_status = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    resultados = db.relationship("ResultadoCobertura", backref="simulacao", lazy=True)


class ResultadoCobertura(db.Model):
    __tablename__ = "resultados_cobertura"

    id = db.Column(db.Integer, primary_key=True)
    simulacao_id = db.Column(db.String(36), db.ForeignKey("simulacoes.id"), nullable=False)
    tipo_contorno = db.Column(db.String(64), nullable=False)  # protegido, interferente, radcom_servico, tv_digital, etc.
    nivel_campo_dbuv_m = db.Column(db.Float, nullable=True)
    geom = db.Column(Geometry(geometry_type="POLYGON", srid=4674), nullable=False)
