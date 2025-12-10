from sqlalchemy.dialects.postgresql import JSONB
from geoalchemy2 import Geometry

from app import db


class EstacaoFM(db.Model):
    __tablename__ = "estacoes_fm"

    id = db.Column(db.Integer, primary_key=True)
    id_mosaico = db.Column(db.String(64), nullable=True)
    id_plano = db.Column(db.String(32), nullable=True)
    uf = db.Column(db.String(2), nullable=True)
    cod_municipio = db.Column(db.String(16), nullable=True)
    municipio = db.Column(db.String(128), nullable=True)
    servico = db.Column(db.String(8), nullable=False)  # FM ou RTR
    canal = db.Column(db.Integer, nullable=False)
    classe = db.Column(db.String(4), nullable=True)
    freq_mhz = db.Column(db.Float, nullable=True)
    erp_max_kw = db.Column(db.Float, nullable=True)
    hnmt_m = db.Column(db.Float, nullable=True)
    erp_por_radial = db.Column(db.JSON().with_variant(JSONB, "postgresql"), nullable=True)
    geom = db.Column(Geometry(geometry_type="POINT", srid=4674), nullable=True)
    antena_id = db.Column(db.Integer, nullable=True)
    categoria = db.Column(db.String(32), nullable=True)  # principal, complementar, reserva
    status = db.Column(db.String(32), nullable=True)
    entidade = db.Column(db.String(255), nullable=True)
    cnpj = db.Column(db.String(32), nullable=True)
    carater = db.Column(db.String(8), nullable=True)
    finalidade = db.Column(db.String(32), nullable=True)
    fistel = db.Column(db.String(64), nullable=True)
    observacoes = db.Column(db.Text, nullable=True)


class EstacaoRadcom(db.Model):
    __tablename__ = "estacoes_radcom"

    id = db.Column(db.Integer, primary_key=True)
    municipio_outorga = db.Column(db.String(128), nullable=False)
    canal = db.Column(db.Integer, nullable=False)
    erp_w = db.Column(db.Float, nullable=False)
    altura_sistema_m = db.Column(db.Float, nullable=False)
    geom = db.Column(Geometry(geometry_type="POINT", srid=4674), nullable=True)
    area_prestacao = db.Column(Geometry(geometry_type="POLYGON", srid=4674), nullable=True)


class EstacaoTV(db.Model):
    __tablename__ = "estacoes_tv"

    id = db.Column(db.Integer, primary_key=True)
    id_plano = db.Column(db.String(32), nullable=True)
    uf = db.Column(db.String(2), nullable=True)
    cod_municipio = db.Column(db.String(16), nullable=True)
    municipio = db.Column(db.String(128), nullable=True)
    servico = db.Column(db.String(16), nullable=False)  # GTVD, RTVD, TV, RTV
    tecnologia = db.Column(db.String(16), nullable=False)  # analogica ou digital
    canal = db.Column(db.Integer, nullable=False)
    classe = db.Column(db.String(16), nullable=True)
    freq_mhz = db.Column(db.Float, nullable=True)
    erp_max_kw = db.Column(db.Float, nullable=True)
    hnmt_m = db.Column(db.Float, nullable=True)
    erp_por_radial = db.Column(db.JSON().with_variant(JSONB, "postgresql"), nullable=True)
    geom = db.Column(Geometry(geometry_type="POINT", srid=4674), nullable=True)
    categoria = db.Column(db.String(32), nullable=True)  # principal, complementar, reserva
    status = db.Column(db.String(32), nullable=True)
    entidade = db.Column(db.String(255), nullable=True)
    cnpj = db.Column(db.String(32), nullable=True)
    carater = db.Column(db.String(8), nullable=True)
    finalidade = db.Column(db.String(32), nullable=True)
    fistel = db.Column(db.String(64), nullable=True)
    fistel_geradora = db.Column(db.String(64), nullable=True)
    observacoes = db.Column(db.Text, nullable=True)


class SetorCensitario(db.Model):
    __tablename__ = "setores_censitarios"

    id = db.Column(db.String(32), primary_key=True)  # código IBGE
    municipio = db.Column(db.String(128), nullable=False)
    tipo = db.Column(db.String(16), nullable=False)  # urbano/rural
    pop_total = db.Column(db.Integer, nullable=True)
    geom = db.Column(Geometry(geometry_type="GEOMETRY", srid=4674), nullable=False)
