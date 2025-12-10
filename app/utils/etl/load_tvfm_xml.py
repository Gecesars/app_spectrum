import os
import xml.etree.ElementTree as ET
from typing import Iterable, List, Optional, Set

import sqlalchemy as sa
from geoalchemy2.elements import WKTElement

from app import create_app, db
from app.models import EstacaoFM, EstacaoTV


def parse_float(value: Optional[str]) -> Optional[float]:
    if value in (None, "", "-"):
        return None
    try:
        return float(str(value).replace(",", "."))
    except Exception:
        return None


def parse_int(value: Optional[str]) -> Optional[int]:
    try:
        return int(value)
    except Exception:
        return None


def make_point(lat_str: Optional[str], lon_str: Optional[str]) -> Optional[WKTElement]:
    lat = parse_float(lat_str)
    lon = parse_float(lon_str)
    if lat is None or lon is None:
        return None
    # PostGIS expects lon/lat order (x,y).
    return WKTElement(f"POINT({lon} {lat})", srid=4674)


def parse_diagrama(diagrama_str: Optional[str]) -> Optional[List[Optional[float]]]:
    """Converte string 'a|b|c' em lista de floats (ou None)."""
    if not diagrama_str:
        return None
    parts = str(diagrama_str).split("|")
    values: List[Optional[float]] = []
    for p in parts:
        if p == "":
            values.append(None)
            continue
        values.append(parse_float(p))
    # Se todos são None, ignora.
    if all(v is None for v in values):
        return None
    return values


def tecnologia_from_attrs(attrs: dict) -> str:
    obs = (attrs.get("Observacoes") or "").upper()
    status = (attrs.get("Status") or "").upper()
    carater = (attrs.get("Carater") or "").upper()
    categoria = (attrs.get("categoriaEstacao") or "").upper()
    tokens_status = status.replace("-", " ").replace("_", " ").split()
    tokens_carater = carater.replace("-", " ").replace("_", " ").split()
    tokens_categoria = categoria.replace("-", " ").replace("_", " ").split()
    if "SBTVD" in obs:
        return "digital"
    if any(tok in {"D", "DIGITAL", "TVD", "RTVD"} for tok in tokens_status):
        return "digital"
    if any(tok in {"D", "DIGITAL", "TVD", "RTVD"} for tok in tokens_carater):
        return "digital"
    if any(tok in {"D", "DIGITAL", "TVD", "RTVD"} for tok in tokens_categoria):
        return "digital"
    return "analogica"


def load_files(file_paths: Iterable[str], truncate: bool = True) -> None:
    if truncate:
        db.session.execute(sa.text("TRUNCATE TABLE estacoes_tv RESTART IDENTITY CASCADE"))
        db.session.execute(sa.text("TRUNCATE TABLE estacoes_fm RESTART IDENTITY CASCADE"))
        db.session.commit()

    existing_tv_ids: Set[str] = set()
    existing_fm_ids: Set[str] = set()

    batch = []
    batch_size = 1000

    for path in file_paths:
        if not os.path.exists(path):
            print(f"Arquivo não encontrado: {path}")
            continue
        print(f"Lendo {path} ...")
        tree = ET.parse(path)
        root = tree.getroot()

        for row in root.findall(".//row"):
            attrs = row.attrib
            servico = (attrs.get("Servico") or "").upper()
            if servico == "TV":
                est = build_tv(attrs)
                id_plano = est.id_plano
                if id_plano and id_plano in existing_tv_ids:
                    continue
                if id_plano:
                    existing_tv_ids.add(id_plano)
                batch.append(est)
            elif servico == "FM":
                est = build_fm(attrs)
                id_plano = est.id_plano or est.id_mosaico
                if id_plano and id_plano in existing_fm_ids:
                    continue
                if id_plano:
                    existing_fm_ids.add(id_plano)
                batch.append(est)
            else:
                continue

            if len(batch) >= batch_size:
                db.session.add_all(batch)
                db.session.commit()
                batch.clear()

    if batch:
        db.session.add_all(batch)
        db.session.commit()
        batch.clear()
    print("Carga concluída.")


def build_tv(attrs: dict) -> EstacaoTV:
    obs = attrs.get("Observacoes")
    tecnologia = tecnologia_from_attrs(attrs)
    ponto = make_point(attrs.get("Latitude"), attrs.get("Longitude"))

    return EstacaoTV(
        id_plano=attrs.get("IdtPlanoBasico") or None,
        uf=attrs.get("UF"),
        cod_municipio=attrs.get("CodMunicipio"),
        municipio=attrs.get("Municipio"),
        servico=attrs.get("Servico") or "TV",
        tecnologia=tecnologia,
        canal=parse_int(attrs.get("Canal")) or 0,
        classe=attrs.get("Classe"),
        freq_mhz=parse_float(attrs.get("Frequencia")),
        erp_max_kw=parse_float(attrs.get("ERP")),
        hnmt_m=parse_float(attrs.get("Altura")),
        erp_por_radial=parse_diagrama(attrs.get("PadraoAntena_dBd")),
        geom=ponto,
        categoria=attrs.get("categoriaEstacao") or attrs.get("Carater"),
        status=attrs.get("Status"),
        entidade=attrs.get("Entidade"),
        cnpj=attrs.get("CNPJ"),
        carater=attrs.get("Carater"),
        finalidade=attrs.get("Finalidade"),
        fistel=attrs.get("Fistel"),
        fistel_geradora=attrs.get("FistelGeradora"),
        observacoes=obs,
    )


def build_fm(attrs: dict) -> EstacaoFM:
    ponto = make_point(attrs.get("Latitude"), attrs.get("Longitude"))
    return EstacaoFM(
        id_mosaico=attrs.get("id") or None,
        id_plano=attrs.get("IdtPlanoBasico") or None,
        uf=attrs.get("UF"),
        cod_municipio=attrs.get("CodMunicipio"),
        municipio=attrs.get("Municipio"),
        servico=attrs.get("Servico") or "FM",
        canal=parse_int(attrs.get("Canal")) or 0,
        classe=attrs.get("Classe"),
        freq_mhz=parse_float(attrs.get("Frequencia")),
        erp_max_kw=parse_float(attrs.get("ERP")),
        hnmt_m=parse_float(attrs.get("Altura")),
        erp_por_radial=parse_diagrama(attrs.get("PadraoAntena_dBd")),
        geom=ponto,
        antena_id=None,
        categoria=attrs.get("categoriaEstacao") or attrs.get("Carater"),
        status=attrs.get("Status"),
        entidade=attrs.get("Entidade"),
        cnpj=attrs.get("CNPJ"),
        carater=attrs.get("Carater"),
        finalidade=attrs.get("Finalidade"),
        fistel=attrs.get("Fistel"),
        observacoes=attrs.get("Observacoes"),
    )


def run() -> None:
    file_paths = [
        os.path.join("data", "plano_basicoTVFM.xml"),
        os.path.join("data", "secudariosTVFM.xml"),
        os.path.join("data", "solicitacoesTVFM.xml"),
    ]
    load_files(file_paths)


if __name__ == "__main__":
    flask_app = create_app()
    with flask_app.app_context():
        run()
