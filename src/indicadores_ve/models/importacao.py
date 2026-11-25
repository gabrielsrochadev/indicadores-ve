"""Classe Importacao (Diagrama de Classes – TED 03).

Representa o envio de uma planilha CSV (RF11). Antes de gravar, o sistema
monta uma PRÉVIA com as linhas válidas e as rejeitadas; só depois da
confirmação do Digitador os lançamentos são gravados.

Associação Importacao 0..1 → * LancamentoMensal ("origina"): cada lançamento
importado guarda o id da importação que o originou.
"""

from __future__ import annotations

from datetime import datetime
from typing import Iterable

from ..excecoes import ErroValidacao
from .enums import StatusImportacao


class Importacao:
    """Prévia e resultado de uma importação de planilha."""

    def __init__(
        self,
        nome_arquivo: str,
        realizada_por: str | None = None,
        status: StatusImportacao = StatusImportacao.PENDENTE,
        data_hora: datetime | None = None,
        validas: Iterable[dict] = (),
        rejeitadas: Iterable[tuple[int, str]] = (),
        id: int | None = None,
    ) -> None:
        nome_arquivo = (nome_arquivo or "").strip()
        if not nome_arquivo:
            raise ErroValidacao("O nome do arquivo é obrigatório.")
        self.id = id
        self._nome_arquivo = nome_arquivo
        self.realizada_por = realizada_por  # login do Digitador
        self._status = StatusImportacao(status)
        self.data_hora = data_hora or datetime.now()
        # validas/rejeitadas preenchidos só ao recarregar do arquivo JSON
        self._validas: list[dict] = [dict(l) for l in validas]
        self._rejeitadas: list[tuple[int, str]] = [(int(n), str(m)) for n, m in rejeitadas]

    @property
    def nome_arquivo(self) -> str:
        return self._nome_arquivo

    @property
    def status(self) -> StatusImportacao:
        return self._status

    # ---- atributos do diagrama (linhasValidas / linhasRejeitadas) como contagens
    @property
    def linhas_validas(self) -> int:
        return len(self._validas)

    @property
    def linhas_rejeitadas(self) -> int:
        return len(self._rejeitadas)

    @property
    def validas(self) -> tuple[dict, ...]:
        """Dados das linhas aprovadas na prévia (somente leitura)."""
        return tuple(dict(linha) for linha in self._validas)

    @property
    def erros(self) -> tuple[tuple[int, str], ...]:
        """(número da linha, mensagem) das linhas rejeitadas."""
        return tuple(self._rejeitadas)

    # ----------------------------------------------------------- prévia
    def _exigir_pendente(self) -> None:
        if self._status is not StatusImportacao.PENDENTE:
            raise ErroValidacao(f"A importação já está {self._status.value}.")

    def adicionar_valida(self, linha: dict) -> None:
        self._exigir_pendente()
        self._validas.append(dict(linha))

    def adicionar_rejeitada(self, numero_linha: int, mensagem: str) -> None:
        self._exigir_pendente()
        self._rejeitadas.append((numero_linha, mensagem))

    def confirmar(self) -> None:
        """Digitador confirma a prévia: a importação pode ser gravada."""
        self._exigir_pendente()
        if not self._validas:
            raise ErroValidacao("Não há linhas válidas para importar.")
        self._status = StatusImportacao.CONFIRMADA

    def cancelar(self) -> None:
        self._exigir_pendente()
        self._status = StatusImportacao.CANCELADA

    # ---------------------------------------------------- métodos especiais
    def __len__(self) -> int:
        """len(importacao) = total de linhas lidas do arquivo (válidas + rejeitadas)."""
        return len(self._validas) + len(self._rejeitadas)

    def __str__(self) -> str:
        return (
            f"{self.nome_arquivo}: {self.linhas_validas} válidas, "
            f"{self.linhas_rejeitadas} com erro ({self.status.value})"
        )

    def __repr__(self) -> str:
        return (
            f"Importacao(nome_arquivo={self.nome_arquivo!r}, validas={self.linhas_validas}, "
            f"rejeitadas={self.linhas_rejeitadas}, status={self.status.value!r})"
        )
