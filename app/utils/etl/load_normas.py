import csv
import os
from typing import Callable, Dict, List, Optional, Sequence

import sqlalchemy as sa

from app import create_app, db
from app.models import (
    NormasFMClasses,
    NormasFMProtecao,
    NormasFMRadcomDistancias,
    NormasRadcom,
    NormasTVDigitalClasses,
    NormasTVAnalogicaClasses,
    NormasTVProtecao,
    NormasTVFMCompatibilidade,
    NormasTVNivelContorno,
)

DATA_DIR = os.path.join("data", "normas")


def load_csv(path: str) -> List[dict]:
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return [row for row in reader]


def load_table(model, rows: Sequence[dict], mapper: Callable[[dict], dict]) -> None:
    if not rows:
        return
    db.session.query(model).delete()
    objs = [model(**mapper(row)) for row in rows]
    db.session.add_all(objs)
    db.session.commit()


def mapper_identity(row: dict) -> dict:
    return row


def to_float(value: Optional[str]) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        return float(str(value).replace(",", "."))
    except Exception:
        return None


def seed_radcom_default() -> None:
    """Insere linha padrão RadCom (25 W, raio 1 km, altura 30 m) se tabela estiver vazia."""
    exists = db.session.query(NormasRadcom).count()
    if exists:
        return
    db.session.add(
        NormasRadcom(erp_max_w=25, raio_servico_km=1.0, altura_max_m=30),
    )
    db.session.commit()
    print("Normas RadCom padrão inseridas (25 W, 1 km, 30 m).")


def run() -> None:
    os.makedirs(DATA_DIR, exist_ok=True)

    loaders: Dict[str, dict] = {
        "normas_fm_classes.csv": {
            "model": NormasFMClasses,
            "mapper": lambda r: {
                "classe": r.get("classe"),
                "erp_max_kw": to_float(r.get("erp_max_kw")),
                "hnmt_max_m": to_float(r.get("hnmt_max_m")),
                "dist_max_contorno66_km": to_float(r.get("dist_max_contorno66_km")),
            },
        },
        "normas_fm_protecao.csv": {
            "model": NormasFMProtecao,
            "mapper": lambda r: {
                "tipo_interferencia": r.get("tipo_interferencia"),
                "delta_f_khz": (
                    int(to_float(r.get("delta_f_khz"))) if to_float(r.get("delta_f_khz")) is not None else None
                ),
                "ci_requerida_db": to_float(r.get("ci_requerida_db")),
            },
        },
        "normas_fm_radcom_distancias.csv": {
            "model": NormasFMRadcomDistancias,
            "mapper": lambda r: {
                "classe_fm": r.get("classe_fm"),
                "situacao": r.get("situacao"),
                "dist_min_km": to_float(r.get("dist_min_km")),
            },
        },
        "normas_radcom.csv": {
            "model": NormasRadcom,
            "mapper": lambda r: {
                "erp_max_w": to_float(r.get("erp_max_w")),
                "raio_servico_km": to_float(r.get("raio_servico_km")),
                "altura_max_m": to_float(r.get("altura_max_m")),
            },
        },
        "normas_tv_digital_classes.csv": {
            "model": NormasTVDigitalClasses,
            "mapper": lambda r: {
                "classe": r.get("classe"),
                "faixa_canal": r.get("faixa_canal"),
                "erp_max_kw": to_float(r.get("erp_max_kw")),
                "hnmt_ref_m": to_float(r.get("hnmt_ref_m")),
                "dist_max_contorno_protegido_km": to_float(
                    r.get("dist_max_contorno_protegido_km")
                ),
            },
        },
        "normas_tv_analogica_classes.csv": {
            "model": NormasTVAnalogicaClasses,
            "mapper": lambda r: {
                "classe": r.get("classe"),
                "faixa_canal": r.get("faixa_canal"),
                "erp_max_kw": to_float(r.get("erp_max_kw")),
                "hnmt_ref_m": to_float(r.get("hnmt_ref_m")),
                "dist_max_contorno_protegido_km": to_float(
                    r.get("dist_max_contorno_protegido_km")
                ),
            },
        },
        "normas_tv_protecao.csv": {
            "model": NormasTVProtecao,
            "mapper": lambda r: {
                "tipo_interferencia": r.get("tipo_interferencia"),
                "tecnologia_desejado": r.get("tecnologia_desejado"),
                "tecnologia_interferente": r.get("tecnologia_interferente"),
                "delta_canal": r.get("delta_canal"),
                "ci_requerida_db": to_float(r.get("ci_requerida_db")),
                "observacao": r.get("observacao"),
            },
        },
        "normas_tv_fm_compatibilidade.csv": {
            "model": NormasTVFMCompatibilidade,
            "mapper": lambda r: {
                "canal_tv": r.get("canal_tv") and int(r.get("canal_tv")),
                "faixa_canais_fm": r.get("faixa_canais_fm"),
                "tipo_interferencia": r.get("tipo_interferencia"),
                "ci_requerida_db": to_float(r.get("ci_requerida_db")),
            },
        },
        "normas_tv_nivel_contorno.csv": {
            "model": NormasTVNivelContorno,
            "mapper": lambda r: {
                "tecnologia": r.get("tecnologia"),
                "faixa_canal": r.get("faixa_canal"),
                "nivel_campo_dbuv_m": to_float(r.get("nivel_campo_dbuv_m")),
            },
        },
    }

    for filename, cfg in loaders.items():
        path = os.path.join(DATA_DIR, filename)
        if not os.path.exists(path):
            continue
        rows = load_csv(path)
        if rows:
            print(f"Carregando {len(rows)} linhas de {filename} ...")
            load_table(cfg["model"], rows, cfg["mapper"])

    # Seed RadCom defaults if nothing loaded
    seed_radcom_default()


if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        run()
