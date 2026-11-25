"""Camada de persistência."""

from .repositorio import Repositorio, RepositorioMemoria
from .repositorio_json import RepositorioJSON

__all__ = ["Repositorio", "RepositorioJSON", "RepositorioMemoria"]
