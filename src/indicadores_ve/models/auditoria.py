"""Classe LogAuditoria (Diagrama de Classes – TED 03).

RNF10: toda operação de escrita (incluir, alterar, importar, exportar,
homologar) gera um registro de quem fez, o quê e quando. O log é imutável:
depois de criado, nenhum atributo pode ser alterado.
"""

from __future__ import annotations

from datetime import datetime

from ..excecoes import ErroValidacao


class LogAuditoria:
    """Registro imutável de uma operação."""

    def __init__(
        self,
        usuario: str,
        acao: str,
        entidade: str,
        valor_anterior: str | None = None,
        valor_novo: str | None = None,
        data_hora: datetime | None = None,
        id: int | None = None,
    ) -> None:
        if not (usuario or "").strip() or not (acao or "").strip():
            raise ErroValidacao("Usuário e ação são obrigatórios no log de auditoria.")
        self._id = id
        self._usuario = usuario  # associação Usuario "gera" (login)
        self._acao = acao
        self._entidade = entidade
        self._valor_anterior = valor_anterior
        self._valor_novo = valor_novo
        self._data_hora = data_hora or datetime.now()

    # Somente leitura: não existem setters (imutabilidade)
    @property
    def id(self) -> int | None:
        return self._id

    @property
    def usuario(self) -> str:
        return self._usuario

    @property
    def acao(self) -> str:
        return self._acao

    @property
    def entidade(self) -> str:
        return self._entidade

    @property
    def valor_anterior(self) -> str | None:
        return self._valor_anterior

    @property
    def valor_novo(self) -> str | None:
        return self._valor_novo

    @property
    def data_hora(self) -> datetime:
        return self._data_hora

    def __str__(self) -> str:
        texto = f"[{self.data_hora:%d/%m/%Y %H:%M}] {self.usuario} – {self.acao} – {self.entidade}"
        if self.valor_anterior is not None or self.valor_novo is not None:
            texto += f" ({self.valor_anterior} → {self.valor_novo})"
        return texto

    def __repr__(self) -> str:
        return (
            f"LogAuditoria(usuario={self.usuario!r}, acao={self.acao!r}, "
            f"entidade={self.entidade!r})"
        )
