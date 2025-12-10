"""
Leitura e interpolação das curvas tabuladas da Recomendação ITU-R P.1546.
Fonte: data/Tabulated field strength values P1546.xls

Suporta interpolação em distância, altura efetiva e frequência (linear no log10 da frequência).
Os tempos disponíveis são 50%, 10% e 1%; escolhemos o tempo mais próximo solicitado.
"""

import math
import os
from functools import lru_cache
from typing import Dict, List, Tuple

import pandas as pd

CURVES_XLS = os.path.join("data", "Tabulated field strength values P1546.xls")


class CurveDataset:
    def __init__(self, freq_mhz: float, time_percent: float, path: str, heights: List[float], distances: List[float], fields: List[List[float]]):
        self.freq_mhz = freq_mhz
        self.time_percent = time_percent
        self.path = path.lower()
        self.heights = heights  # list of m (ex: 10, 20, 37.5, ...)
        self.distances = distances  # list of km
        self.fields = fields  # matrix [len(distances) x len(heights)] in dBµV/m


@lru_cache(maxsize=1)
def load_curves() -> List[CurveDataset]:
    datasets: List[CurveDataset] = []
    
    # Verifica se o arquivo existe antes de tentar abrir
    if not os.path.exists(CURVES_XLS):
        raise FileNotFoundError(f"Arquivo não encontrado: {CURVES_XLS}")

    xl = pd.ExcelFile(CURVES_XLS)
    
    for name in xl.sheet_names:
        # Lê a aba sem cabeçalho para processar manualmente
        df = pd.read_excel(CURVES_XLS, sheet_name=name, header=None)
        
        # Leitura robusta dos metadados (linhas fixas)
        try:
            freq_cell = str(df.iloc[1, 1])
            freq_mhz = float(freq_cell.split()[0])
            time_percent = float(df.iloc[2, 1])
            path_val = str(df.iloc[3, 1]).strip()
        except (IndexError, ValueError):
            # Pula abas que não sigam o padrão esperado
            continue

        # Encontra a linha de cabeçalho da tabela (onde começa "Number of distances")
        header_row_matches = df.index[df.iloc[:, 0].astype(str).str.contains("Number of distances", na=False)].tolist()
        if not header_row_matches:
            continue
        hidx = header_row_matches[0]

        # --- CORREÇÃO APLICADA AQUI ---
        # Identifica as colunas que contêm alturas válidas.
        # A tabela ITU P.1546 possui uma coluna final com cabeçalho "0.0" que representa "Max Field".
        # Devemos ignorá-la para não distorcer a interpolação de alturas (pois 0.0 seria tratado como h=0m).
        heights = []
        valid_cols = [] # Guarda os índices das colunas válidas
        
        col = 2 # Alturas começam na coluna C (índice 2)
        while col < df.shape[1]:
            val = df.iat[hidx, col]
            if pd.isna(val):
                break
            
            h_val = float(val)
            # Ignora se for 0.0 (indicativo de Max Field/Espaço Livre nesta tabela específica)
            if h_val != 0.0:
                heights.append(h_val)
                valid_cols.append(col)
            
            col += 1
        
        # Se não encontrou alturas válidas, pula
        if not heights:
            continue

        distances: List[float] = []
        fields: List[List[float]] = []


        # Lê os dados linha a linha
        row = hidx + 1
        while row < df.shape[0]:
            dist_val = df.iat[row, 1]
            
            # Para de ler se a distância for inválida ou vazia
            if pd.isna(dist_val):
                break
            
            distances.append(float(dist_val))
            
            row_fields = []
            # Lê apenas as colunas identificadas como alturas válidas
            for col_idx in valid_cols:
                val = df.iat[row, col_idx]
                row_fields.append(float(val))
            
            fields.append(row_fields)
            row += 1

        datasets.append(CurveDataset(freq_mhz, time_percent, path_val, heights, distances, fields))
        
    return datasets


def _find_bracketing(values: List[float], x: float) -> Tuple[int, int, float]:
    """Retorna (i0, i1, t) tal que values[i0] <= x <= values[i1] e t é fração entre eles."""
    if not values:
        return 0, 0, 0.0
    if x <= values[0]:
        return 0, 0, 0.0
    if x >= values[-1]:
        return len(values) - 1, len(values) - 1, 0.0
    
    for i in range(len(values) - 1):
        v0, v1 = values[i], values[i + 1]
        if v0 <= x <= v1:
            # Evita divisão por zero se v1 == v0
            t = 0.0 if v1 == v0 else (x - v0) / (v1 - v0)
            return i, i + 1, t
            
    return len(values) - 1, len(values) - 1, 0.0


def _interp_dataset(ds: CurveDataset, dist_km: float, h_eff_m: float) -> float:
    # Interpolação Logarítmica para Distância geralmente é preferida em propagação, 
    # mas o método abaixo segue a interpolação linear padrão do código original.
    # Para P.1546 rigorosa, distância costuma ser log e altura log também.
    # Aqui mantivemos linear conforme o original para consistência, mas é um ponto de atenção.
    
    i0, i1, td = _find_bracketing(ds.distances, dist_km)
    j0, j1, th = _find_bracketing(ds.heights, h_eff_m)

    def val(i, j):
        return ds.fields[i][j]

    v00 = val(i0, j0)
    v01 = val(i0, j1)
    v10 = val(i1, j0)
    v11 = val(i1, j1)

    # Interpolação bilinear
    v0 = v00 + (v01 - v00) * th
    v1 = v10 + (v11 - v10) * th
    return v0 + (v1 - v0) * td


def field_strength_p1546(freq_mhz: float, dist_km: float, h_eff_m: float, time_percent: float = 50.0, path: str = "Land") -> float:
    """Interpolação da intensidade de campo (dBµV/m) a partir das curvas tabuladas."""
    datasets = load_curves()
    
    if not datasets:
        raise ValueError("Nenhuma curva foi carregada. Verifique o arquivo de dados.")

    path = path.lower()
    
    # 1. Filtra por path (Land, Sea, Cold Sea, Warm Sea)
    ds_path = [d for d in datasets if d.path == path]
    if not ds_path:
        # Fallback se não encontrar o path exato
        print(f"Aviso: Path '{path}' não encontrado. Usando todos os datasets disponíveis.")
        ds_path = datasets

    # 2. Filtra pelo tempo mais próximo (1%, 10%, 50%)
    times = sorted({d.time_percent for d in ds_path})
    if not times:
        raise ValueError(f"Não foram encontrados dados de tempo para o path '{path}'")
        
    time_closest = min(times, key=lambda t: abs(t - time_percent))
    ds_time = [d for d in ds_path if d.time_percent == time_closest]

    # 3. Interpolação em Frequência (Logarítmica)
    freqs = sorted({d.freq_mhz for d in ds_time})
    
    # Caso fora dos limites ou exato
    if freq_mhz <= freqs[0]:
        f0 = f1 = freqs[0]
    elif freq_mhz >= freqs[-1]:
        f0 = f1 = freqs[-1]
    else:
        # Encontra o par de frequências que cerca a desejada
        f0 = freqs[0]
        f1 = freqs[-1]
        for k in range(len(freqs) - 1):
            if freqs[k] <= freq_mhz <= freqs[k + 1]:
                f0, f1 = freqs[k], freqs[k + 1]
                break
    
    # Pega os datasets correspondentes às frequências f0 e f1
    # Nota: Assume-se que só há um dataset por (freq, time, path)
    d0 = [d for d in ds_time if d.freq_mhz == f0][0]
    d1 = [d for d in ds_time if d.freq_mhz == f1][0]

    v0 = _interp_dataset(d0, dist_km, h_eff_m)
    
    if f0 == f1:
        return v0
        
    v1 = _interp_dataset(d1, dist_km, h_eff_m)
    
    # Interpolação linear no logaritmo da frequência
    w = (math.log10(freq_mhz) - math.log10(f0)) / (math.log10(f1) - math.log10(f0))
    return v0 + (v1 - v0) * w

# --- Exemplo de uso ---
if __name__ == "__main__":
    try:
        # Teste rápido
        e_field = field_strength_p1546(freq_mhz=100.0, dist_km=10.0, h_eff_m=30.0, time_percent=50.0, path="Land")
        print(f"Resultado estimado: {e_field:.2f} dBuV/m")
    except Exception as e:
        print(f"Erro ao executar: {e}")