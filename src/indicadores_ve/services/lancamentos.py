"""Lançamento de dados (RF01–RF04, RF12 – UC03 e UC05).

O método registrar() recebe QUALQUER RegistroEpidemiologico (lançamento
mensal, ciclo do PNCD ou LIRAa) e trata todos do mesmo jeito: isso é
polimorfismo. Cada objeto sabe se validar (validar) e se identificar (chave).

Regras aplicadas em ordem (diagrama de atividades – Figura 4 da SRS):
1. permissão do perfil (RN03)
2. validação do próprio registro (RN05, A08)
3. período homologado? → bloqueia (RN11)
4. registro já existe? → só substitui com confirmação (RN04)
5. grava e registra auditoria (RNF10)
"""

from __future__ import annotations

from datetime import datetime
from typing import Callable

from ..excecoes import PeriodoHomologado, RegistroDuplicado
from ..models import LancamentoMensal, OrigemDado, Permissao, RegistroEpidemiologico, Usuario
from ..persistence import Repositorio
from .auditoria import ServicoAuditoria
from .autenticacao import exigir_permissao


class ServicoLancamentos:
    def __init__(
        self,
        repositorio: Repositorio,
        auditoria: ServicoAuditoria,
        relogio: Callable[[], datetime] = datetime.now,
    ) -> None:
        self._repo = repositorio
        self._auditoria = auditoria
        self._relogio = relogio

    # --------------------------------------------------------- regras
    def verificar_periodo_aberto(self, registro: RegistroEpidemiologico) -> None:
        """RN11: não altera dados de quadrimestre homologado."""
        relatorio = self._repo.obter_relatorio(registro.ano, registro.quadrimestre)
        if relatorio is not None and relatorio.esta_bloqueado:
            raise PeriodoHomologado(
                f"O {relatorio.quadrimestre}º quadrimestre de {relatorio.ano} está homologado. "
                "Peça ao Coordenador a reabertura do período."
            )

    def existe(self, registro: RegistroEpidemiologico) -> bool:
        return self._repo.obter_registro(registro.chave()) is not None

    # ----------------------------------------------------- operações
    def registrar(
        self,
        usuario: Usuario,
        registro: RegistroEpidemiologico,
        confirmar_substituicao: bool = False,
        salvar: bool = True,
    ) -> RegistroEpidemiologico:
        exigir_permissao(usuario, Permissao.LANCAR_DADOS)
        registro.validar(self._relogio().date())
        self.verificar_periodo_aberto(registro)

        anterior = self._repo.obter_registro(registro.chave())
        if anterior is not None and not confirmar_substituicao:
            raise RegistroDuplicado(
                f"Já existe um registro para este período ({anterior}). "
                "Confirme a substituição para continuar."
            )
        if anterior is not None:
            registro.id = anterior.id

        registro.registrado_por = usuario
        self._repo.salvar_registro(registro)
        self._auditoria.registrar(
            usuario.login,
            "substituir" if anterior else "incluir",
            type(registro).__name__,
            anterior,
            registro,
        )
        if salvar:
            self._repo.salvar()
        return registro

    def lancar_valor(
        self,
        usuario: Usuario,
        codigo_indicador: str,
        ano: int,
        mes: int,
        valor: float,
        confirmar_substituicao: bool = False,
    ) -> LancamentoMensal:
        """Atalho para o caso mais comum: total mensal de um indicador."""
        indicador = self._repo.buscar_indicador(codigo_indicador)
        lancamento = LancamentoMensal(indicador, ano, mes, valor, OrigemDado.DIGITACAO)
        return self.registrar(usuario, lancamento, confirmar_substituicao)

    def excluir(self, usuario: Usuario, registro: RegistroEpidemiologico) -> None:
        """RF01: excluir um lançamento (também respeita o período homologado)."""
        exigir_permissao(usuario, Permissao.LANCAR_DADOS)
        self.verificar_periodo_aberto(registro)
        removido = self._repo.remover_registro(registro.chave())
        self._auditoria.registrar(usuario.login, "excluir", type(removido).__name__, removido, None)
        self._repo.salvar()
