"""Classe RelatorioQuadrimestral (Diagrama de Classes – TED 03).

Controla a homologação do quadrimestre (RF14): depois de homologado, os
dados do período ficam bloqueados (RN11) até uma reabertura justificada
pelo Coordenador.

Dependência "consolida" → LancamentoMensal: o relatório não guarda os
lançamentos; recebe a lista no método consolidar() e calcula os totais
(RN06: totais nunca são digitados).
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import TYPE_CHECKING, Iterable

from ..excecoes import AcessoNegado, ErroValidacao
from .enums import StatusRelatorio
from .usuario import Permissao

if TYPE_CHECKING:
    from .registros import LancamentoMensal
    from .usuario import Usuario


class RelatorioQuadrimestral:
    """Relatório de um quadrimestre (1º jan.–abr.; 2º mai.–ago.; 3º set.–dez. – RN10)."""

    TAMANHO_MINIMO_JUSTIFICATIVA = 10

    def __init__(
        self,
        ano: int,
        quadrimestre: int,
        status: StatusRelatorio = StatusRelatorio.RASCUNHO,
        versao: int = 1,
        destaques: str = "",
        homologado_em: datetime | None = None,
        homologado_por: str | None = None,
        justificativas: Iterable[str] = (),
        id: int | None = None,
    ) -> None:
        if not isinstance(ano, int) or not 2000 <= ano <= 2100:
            raise ErroValidacao("Ano inválido.")
        if quadrimestre not in (1, 2, 3):
            raise ErroValidacao("O quadrimestre deve ser 1, 2 ou 3 (RN10).")
        self.id = id
        self._ano = ano
        self._quadrimestre = quadrimestre
        self._status = StatusRelatorio(status)
        self._versao = versao
        self.destaques = destaques
        self._homologado_em = homologado_em
        self._homologado_por = homologado_por  # associação Usuario "homologa" (login)
        self._justificativas: list[str] = list(justificativas)  # histórico de reaberturas

    # ----------------------------------------------------------- propriedades
    @property
    def ano(self) -> int:
        return self._ano

    @property
    def quadrimestre(self) -> int:
        return self._quadrimestre

    @property
    def status(self) -> StatusRelatorio:
        return self._status

    @property
    def versao(self) -> int:
        return self._versao

    @property
    def homologado_em(self) -> datetime | None:
        return self._homologado_em

    @property
    def homologado_por(self) -> str | None:
        return self._homologado_por

    @property
    def justificativas(self) -> tuple[str, ...]:
        return tuple(self._justificativas)

    @property
    def meses(self) -> range:
        """RN10: meses do quadrimestre (ex.: 2º → 5, 6, 7, 8)."""
        inicio = (self.quadrimestre - 1) * 4 + 1
        return range(inicio, inicio + 4)

    @property
    def esta_bloqueado(self) -> bool:
        """RN11: período homologado não aceita alteração."""
        return self._status is StatusRelatorio.HOMOLOGADO

    def contem(self, ano: int, mes: int) -> bool:
        return ano == self.ano and mes in self.meses

    # ---------------------------------------------------------- homologação
    @staticmethod
    def _exigir_coordenador(usuario: "Usuario") -> None:
        if not usuario.tem_permissao(Permissao.HOMOLOGAR_RELATORIO):
            raise AcessoNegado("Somente o Coordenador da VE pode homologar ou reabrir relatórios.")

    def homologar(self, usuario: "Usuario", agora: datetime | None = None) -> None:
        """RF14: homologa o quadrimestre e bloqueia o período."""
        self._exigir_coordenador(usuario)
        if self.esta_bloqueado:
            raise ErroValidacao("Este relatório já está homologado.")
        self._status = StatusRelatorio.HOMOLOGADO
        self._homologado_em = agora or datetime.now()
        self._homologado_por = usuario.login

    def reabrir(self, usuario: "Usuario", justificativa: str) -> None:
        """RN11: reabertura só com justificativa; gera nova versão do relatório."""
        self._exigir_coordenador(usuario)
        if not self.esta_bloqueado:
            raise ErroValidacao("Só é possível reabrir um relatório homologado.")
        justificativa = (justificativa or "").strip()
        if len(justificativa) < self.TAMANHO_MINIMO_JUSTIFICATIVA:
            raise ErroValidacao(
                f"A justificativa deve ter pelo menos {self.TAMANHO_MINIMO_JUSTIFICATIVA} caracteres."
            )
        self._justificativas.append(justificativa)
        self._status = StatusRelatorio.REABERTO
        self._versao += 1

    # --------------------------------------------------------- consolidação
    def consolidar(self, lancamentos: Iterable["LancamentoMensal"]) -> dict[str, float]:
        """RN06: soma, por indicador, os lançamentos que caem no quadrimestre."""
        totais: dict[str, float] = defaultdict(int)
        for lancamento in lancamentos:
            if self.contem(lancamento.ano, lancamento.mes):
                totais[lancamento.indicador.codigo] += lancamento.valor
        return dict(totais)

    # ---------------------------------------------------- métodos especiais
    def __str__(self) -> str:
        return f"{self.quadrimestre}º quadrimestre/{self.ano} – {self.status.value} (v{self.versao})"

    def __repr__(self) -> str:
        return (
            f"RelatorioQuadrimestral(ano={self.ano}, quadrimestre={self.quadrimestre}, "
            f"status={self.status.value!r}, versao={self.versao})"
        )
