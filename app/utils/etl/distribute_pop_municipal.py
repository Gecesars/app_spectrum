"""
Distribui população municipal (Censo 2022) proporcionalmente à área dos setores censitários.

Entrada: arquivo Excel com população total por município (sheet 'Municípios') no path default
         data/CD2022_Populacao_Coletada_Imputada_e_Total_Municipio_e_UF_20231222.xlsx
Algoritmo:
  - Lê população total por município (UF + código do município) => pop_total_mun.
  - Calcula área de cada setor (geografia) e soma por município.
  - Define pop_total do setor = pop_total_mun * (area_setor / area_mun).

Uso:
  docker-compose exec web python -m app.utils.etl.distribute_pop_municipal
"""

import pandas as pd
import sqlalchemy as sa
from flask import current_app

from app import create_app, db


def load_pop_municipal(xlsx_path: str):
    df = pd.read_excel(xlsx_path, sheet_name="Municípios", header=None, engine="openpyxl")
    # Colunas: [NaN, UF_SIGLA, COD_UF, COD_MUN (5d), NOME, POP_COLETADA, POP_IMPUTADA, POP_TOTAL]
    df = df.rename(columns={1: "uf", 2: "cod_uf", 3: "cod_mun5", 4: "nome", 7: "pop_total"})
    df = df[df["nome"].notna() & df["pop_total"].notna()]
    df["cod_uf_num"] = pd.to_numeric(df["cod_uf"], errors="coerce")
    df["cod_mun5_num"] = pd.to_numeric(df["cod_mun5"], errors="coerce")
    df = df[df["cod_uf_num"].notna() & df["cod_mun5_num"].notna()]
    df["cod_mun"] = df.apply(
        lambda r: str(int(r["cod_uf_num"])).zfill(2) + str(int(r["cod_mun5_num"])).zfill(5), axis=1
    )
    return df[["cod_mun", "pop_total"]]


def distribute(xlsx_path: str):
    df = load_pop_municipal(xlsx_path)
    # Tabela temporária com população municipal
    with db.engine.begin() as conn:
        conn.execute(sa.text("DROP TABLE IF EXISTS tmp_pop_mun"))
        conn.execute(sa.text("CREATE TEMP TABLE tmp_pop_mun(cod_mun text primary key, pop_total numeric)"))
        conn.execute(sa.text("INSERT INTO tmp_pop_mun(cod_mun, pop_total) VALUES (:cod_mun, :pop_total)"), df.to_dict(orient="records"))

        # Atualiza pop_total dos setores proporcional à área
        sql = sa.text(
            """
            WITH area_mun AS (
              SELECT substring(id from 1 for 7) AS cod_mun,
                     SUM(ST_Area(geom::geography)/1e6) AS area_sum_km2
              FROM setores_censitarios
              GROUP BY 1
            )
            UPDATE setores_censitarios s
            SET pop_total = pm.pop_total * (ST_Area(s.geom::geography)/1e6) / am.area_sum_km2
            FROM tmp_pop_mun pm
            JOIN area_mun am ON am.cod_mun = pm.cod_mun
            WHERE substring(s.id from 1 for 7) = pm.cod_mun
              AND am.area_sum_km2 > 0;
            """
        )
        conn.execute(sql)
    print("Distribuição concluída.")


def main():
    app = create_app()
    with app.app_context():
        path = current_app.config.get(
            "POP_MUNICIPAL_XLSX",
            "data/CD2022_Populacao_Coletada_Imputada_e_Total_Municipio_e_UF_20231222.xlsx",
        )
        distribute(path)


if __name__ == "__main__":
    main()
