"""Ponto único de montagem dos serviços.

A interface (menu) e os testes criam um Sistema e usam os serviços por ele.
O relógio pode ser trocado nos testes para simular datas (ex.: sessão expirada).
"""

from __future__ import annotations

from datetime import datetime
from typing import Callable

from ..persistence import Repositorio
from .auditoria import ServicoAuditoria
from .autenticacao import ServicoAutenticacao
from .importacao import ServicoImportacao
from .indicadores import ServicoIndicadores
from .lancamentos import ServicoLancamentos
from .relatorios import ServicoRelatorios
from .usuarios import ServicoUsuarios


class Sistema:
    def __init__(self, repositorio: Repositorio, relogio: Callable[[], datetime] = datetime.now) -> None:
        self.repositorio = repositorio
        self.auditoria = ServicoAuditoria(repositorio, relogio)
        self.autenticacao = ServicoAutenticacao(repositorio, self.auditoria, relogio)
        self.usuarios = ServicoUsuarios(repositorio, self.auditoria)
        self.lancamentos = ServicoLancamentos(repositorio, self.auditoria, relogio)
        self.importacao = ServicoImportacao(repositorio, self.lancamentos, self.auditoria, relogio)
        self.indicadores = ServicoIndicadores(repositorio)
        self.relatorios = ServicoRelatorios(repositorio, self.indicadores, self.auditoria, relogio)

    def __repr__(self) -> str:
        return f"Sistema(repositorio={type(self.repositorio).__name__})"
