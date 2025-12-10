from app import db


class NormasFMClasses(db.Model):
    __tablename__ = "normas_fm_classes"

    classe = db.Column(db.String(4), primary_key=True)
    erp_max_kw = db.Column(db.Float, nullable=False)
    hnmt_max_m = db.Column(db.Float, nullable=False)
    dist_max_contorno66_km = db.Column(db.Float)


class NormasFMProtecao(db.Model):
    __tablename__ = "normas_fm_protecao"

    id = db.Column(db.Integer, primary_key=True)
    tipo_interferencia = db.Column(db.String(32), nullable=False)  # cocanal, adjacente_200khz, etc.
    delta_f_khz = db.Column(db.Integer, nullable=True)
    ci_requerida_db = db.Column(db.Float, nullable=False)


class NormasFMRadcomDistancias(db.Model):
    __tablename__ = "normas_fm_radcom_distancias"

    id = db.Column(db.Integer, primary_key=True)
    classe_fm = db.Column(db.String(4), nullable=False)
    situacao = db.Column(db.String(32), nullable=False)  # cocanal, adjacente_1, etc.
    dist_min_km = db.Column(db.Float, nullable=False)


class NormasRadcom(db.Model):
    __tablename__ = "normas_radcom"

    id = db.Column(db.Integer, primary_key=True)
    erp_max_w = db.Column(db.Float, nullable=False)
    raio_servico_km = db.Column(db.Float, nullable=False)
    altura_max_m = db.Column(db.Float, nullable=False)


class NormasTVDigitalClasses(db.Model):
    __tablename__ = "normas_tv_digital_classes"

    id = db.Column(db.Integer, primary_key=True)
    classe = db.Column(db.String(16), nullable=False)
    faixa_canal = db.Column(db.String(32), nullable=False)  # vhf_baixo, vhf_alto, uhf
    erp_max_kw = db.Column(db.Float, nullable=False)
    hnmt_ref_m = db.Column(db.Float, nullable=False)
    dist_max_contorno_protegido_km = db.Column(db.Float, nullable=True)


class NormasTVAnalogicaClasses(db.Model):
    __tablename__ = "normas_tv_analogica_classes"

    id = db.Column(db.Integer, primary_key=True)
    classe = db.Column(db.String(16), nullable=False)
    faixa_canal = db.Column(db.String(32), nullable=False)
    erp_max_kw = db.Column(db.Float, nullable=False)
    hnmt_ref_m = db.Column(db.Float, nullable=False)
    dist_max_contorno_protegido_km = db.Column(db.Float, nullable=True)


class NormasTVProtecao(db.Model):
    __tablename__ = "normas_tv_protecao"

    id = db.Column(db.Integer, primary_key=True)
    tipo_interferencia = db.Column(db.String(32), nullable=False)  # cocanal, adjacente, batimento_fi, etc.
    tecnologia_desejado = db.Column(db.String(16), nullable=False)  # analogico, digital
    tecnologia_interferente = db.Column(db.String(16), nullable=False)
    delta_canal = db.Column(db.String(8), nullable=True)  # n, n-1, n+1, n-7, etc.
    ci_requerida_db = db.Column(db.Float, nullable=False)
    observacao = db.Column(db.String(255), nullable=True)


class NormasTVFMCompatibilidade(db.Model):
    __tablename__ = "normas_tv_fm_compatibilidade"

    id = db.Column(db.Integer, primary_key=True)
    canal_tv = db.Column(db.Integer, nullable=False)  # 5 ou 6
    faixa_canais_fm = db.Column(db.String(64), nullable=False)
    tipo_interferencia = db.Column(db.String(32), nullable=False)
    ci_requerida_db = db.Column(db.Float, nullable=False)


class NormasTVNivelContorno(db.Model):
    __tablename__ = "normas_tv_nivel_contorno"

    id = db.Column(db.Integer, primary_key=True)
    tecnologia = db.Column(db.String(16), nullable=False)  # analogica ou digital
    faixa_canal = db.Column(db.String(32), nullable=False)
    nivel_campo_dbuv_m = db.Column(db.Float, nullable=False)
