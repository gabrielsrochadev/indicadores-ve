"""Serviço de auditoria (RNF10): quem fez o quê, em qual registro e quando."""

from __future__ import annotations

from datetime import datetime
from typing import Callable

from ..models import LogAuditoria
from ..persistence import Repositorio


class ServicoAuditoria:
    def __init__(self, repositorio: Repositorio, relogio: Callable[[], datetime] = datetime.now) -> None:
        self._repo = repositorio
        self._relogio = relogio

    def registrar(
        self,
        usuario: str,
        acao: str,
        entidade: str,
        valor_anterior: object = None,
        valor_novo: object = None,
    ) -> LogAuditoria:
        log = LogAuditoria(
            usuario=usuario,
            acao=acao,
            entidade=entidade,
            valor_anterior=None if valor_anterior is None else str(valor_anterior),
            valor_novo=None if valor_novo is None else str(valor_novo),
            data_hora=self._relogio(),
            id=self._repo.proximo_id("logs"),
        )
        return self._repo.adicionar_log(log)

    def listar(self, usuario: str | None = None, acao: str | None = None) -> list[LogAuditoria]:
        logs = self._repo.listar_logs()
        if usuario:
            logs = [l for l in logs if l.usuario == usuario]
        if acao:
            logs = [l for l in logs if l.acao == acao]
        return logs
