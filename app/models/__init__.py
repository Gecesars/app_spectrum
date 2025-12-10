"""Pacote de modelos SQLAlchemy/GeoAlchemy2."""

from app.models.normas import (
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
from app.models.estacoes import (
    EstacaoFM,
    EstacaoRadcom,
    EstacaoTV,
    SetorCensitario,
)
from app.models.simulacoes import Simulacao, ResultadoCobertura

__all__ = [
    "NormasFMClasses",
    "NormasFMProtecao",
    "NormasFMRadcomDistancias",
    "NormasRadcom",
    "NormasTVDigitalClasses",
    "NormasTVAnalogicaClasses",
    "NormasTVProtecao",
    "NormasTVFMCompatibilidade",
    "NormasTVNivelContorno",
    "EstacaoFM",
    "EstacaoRadcom",
    "EstacaoTV",
    "SetorCensitario",
    "Simulacao",
    "ResultadoCobertura",
]
