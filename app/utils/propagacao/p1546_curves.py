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
        self.heights = heights  # list of m
        self.distances = distances  # list of km
        self.fields = fields  # matrix [len(distances) x len(heights)] in dBµV/m


@lru_cache(maxsize=1)
def load_curves() -> List[CurveDataset]:
    datasets: List[CurveDataset] = []
    xl = pd.ExcelFile(CURVES_XLS)
    for name in xl.sheet_names:
        df = pd.read_excel(CURVES_XLS, sheet_name=name, header=None)
        freq_cell = str(df.iloc[1, 1])
        freq_mhz = float(freq_cell.split()[0])
        time_percent = float(df.iloc[2, 1])
        path = str(df.iloc[3, 1]).strip()

        # Find header row
        header_row = df.index[df.iloc[:, 0].astype(str).str.contains("Number of distances", na=False)].tolist()
        if not header_row:
            continue
        hidx = header_row[0]

        # Heights are on header row, columns from 2 onward until NaN
        heights = []
        col = 2
        while col < df.shape[1]:
            val = df.iat[hidx, col]
            if pd.isna(val):
                break
            heights.append(float(val))
            col += 1

        distances: List[float] = []
        fields: List[List[float]] = []

        row = hidx + 1
        while row < df.shape[0]:
            dist = df.iat[row, 1]
            if pd.isna(dist):
                break
            distances.append(float(dist))
            row_fields = []
            for i in range(len(heights)):
                val = df.iat[row, 2 + i]
                row_fields.append(float(val))
            fields.append(row_fields)
            row += 1

        datasets.append(CurveDataset(freq_mhz, time_percent, path, heights, distances, fields))
    return datasets


def _find_bracketing(values: List[float], x: float) -> Tuple[int, int, float]:
    """Retorna (i0, i1, t) tal que values[i0] <= x <= values[i1] e t é fração entre eles."""
    if x <= values[0]:
        return 0, 0, 0.0
    if x >= values[-1]:
        return len(values) - 1, len(values) - 1, 0.0
    for i in range(len(values) - 1):
        v0, v1 = values[i], values[i + 1]
        if v0 <= x <= v1:
            t = 0.0 if v1 == v0 else (x - v0) / (v1 - v0)
            return i, i + 1, t
    return len(values) - 1, len(values) - 1, 0.0


def _interp_dataset(ds: CurveDataset, dist_km: float, h_eff_m: float) -> float:
    i0, i1, td = _find_bracketing(ds.distances, dist_km)
    j0, j1, th = _find_bracketing(ds.heights, h_eff_m)

    def val(i, j):
        return ds.fields[i][j]

    v00 = val(i0, j0)
    v01 = val(i0, j1)
    v10 = val(i1, j0)
    v11 = val(i1, j1)

    v0 = v00 + (v01 - v00) * th
    v1 = v10 + (v11 - v10) * th
    return v0 + (v1 - v0) * td


def field_strength_p1546(freq_mhz: float, dist_km: float, h_eff_m: float, time_percent: float = 50.0, path: str = "Land") -> float:
    """Interpolação da intensidade de campo (dBµV/m) a partir das curvas tabuladas."""
    datasets = load_curves()
    path = path.lower()
    # Filtra por path e tempo mais próximo
    ds_path = [d for d in datasets if d.path.lower() == path.lower()]
    if not ds_path:
        ds_path = datasets
    times = sorted({d.time_percent for d in ds_path})
    time_closest = min(times, key=lambda t: abs(t - time_percent))
    ds_time = [d for d in ds_path if d.time_percent == time_closest]

    # Frequências disponíveis
    freqs = sorted({d.freq_mhz for d in ds_time})
    if freq_mhz <= freqs[0]:
        f0 = f1 = freqs[0]
    elif freq_mhz >= freqs[-1]:
        f0 = f1 = freqs[-1]
    else:
        for k in range(len(freqs) - 1):
            if freqs[k] <= freq_mhz <= freqs[k + 1]:
                f0, f1 = freqs[k], freqs[k + 1]
                break
    d0 = [d for d in ds_time if d.freq_mhz == f0][0]
    d1 = [d for d in ds_time if d.freq_mhz == f1][0]

    v0 = _interp_dataset(d0, dist_km, h_eff_m)
    if f0 == f1:
        return v0
    v1 = _interp_dataset(d1, dist_km, h_eff_m)
    w = (math.log10(freq_mhz) - math.log10(f0)) / (math.log10(f1) - math.log10(f0))
    return v0 + (v1 - v0) * w
