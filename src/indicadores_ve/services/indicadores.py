"""Cálculo de indicadores, painel, comparativo e filtros
(RF05, RF06, RF07, RF13 – UC06, UC07, UC08; RN06, RN07, RN10).

RN06: nenhum total é digitado. Todo total é a soma dos lançamentos mensais,
calculada na hora da consulta. Por isso, ao alterar um valor mensal, todos
os totais e variações que dependem dele já mudam automaticamente (CA de RF13).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from ..excecoes import ErroValidacao
from ..models import Indicador, Permissao, Usuario
from ..models.registros import quadrimestre_do_mes
from ..persistence import Repositorio
from .autenticacao import exigir_permissao

NOMES_MESES = ("jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez")


# =========================================================================
# Período (RN10)
# =========================================================================
@dataclass(frozen=True)
class Periodo:
    """Um mês, um quadrimestre ou um ano. frozen=True gera __eq__ e __hash__."""

    tipo: str  # "mes", "quadrimestre" ou "ano"
    ano: int
    numero: int | None = None  # mês (1–12) ou quadrimestre (1–3); vazio para "ano"

    def __post_init__(self) -> None:
        if self.tipo not in ("mes", "quadrimestre", "ano"):
            raise ErroValidacao("Tipo de período inválido: use mês, quadrimestre ou ano.")
        if self.tipo == "mes" and self.numero not in range(1, 13):
            raise ErroValidacao("Mês inválido.")
        if self.tipo == "quadrimestre" and self.numero not in (1, 2, 3):
            raise ErroValidacao("Quadrimestre inválido (1, 2 ou 3).")

    @classmethod
    def mes(cls, ano: int, mes: int) -> "Periodo":
        return cls("mes", ano, mes)

    @classmethod
    def quadrimestre(cls, ano: int, quadrimestre: int) -> "Periodo":
        return cls("quadrimestre", ano, quadrimestre)

    @classmethod
    def anual(cls, ano: int) -> "Periodo":
        return cls("ano", ano)

    @property
    def meses(self) -> list[int]:
        if self.tipo == "mes":
            return [self.numero]
        if self.tipo == "quadrimestre":
            inicio = (self.numero - 1) * 4 + 1
            return list(range(inicio, inicio + 4))
        return list(range(1, 13))

    def mesmo_periodo_ano_anterior(self) -> "Periodo":
        return Periodo(self.tipo, self.ano - 1, self.numero)

    def contem(self, ano: int, mes: int) -> bool:
        return ano == self.ano and mes in self.meses

    def __str__(self) -> str:
        if self.tipo == "mes":
            return f"{self.numero:02d}/{self.ano}"
        if self.tipo == "quadrimestre":
            return f"{self.numero}º quadrimestre/{self.ano}"
        return str(self.ano)


# =========================================================================
# Estruturas de resultado
# =========================================================================
@dataclass
class LinhaComparativo:
    codigo: str
    nome: str
    valor_atual: float
    valor_base: float
    diferenca: float
    variacao: float | None  # None quando a base é zero (RN07 → "—")


@dataclass
class Cartao:
    titulo: str
    valor: float | str
    valor_ano_anterior: float | None = None
    variacao: float | None = None


@dataclass
class ResumoPainel:
    periodo: Periodo
    cartoes: list[Cartao] = field(default_factory=list)
    principais_agravos: list[tuple[str, float]] = field(default_factory=list)
    serie_mensal: dict[str, float] = field(default_factory=dict)


# Cartões do painel principal (protótipo – tela "Dashboard")
CARTOES_PAINEL = (
    ("Notificações (SINAN)", {"modulo": "SINAN"}),
    ("Exames enviados (LACEN)", {"modulo": "LACEN", "grupo": "Exames LACEN"}),
    ("Nascidos vivos (SINASC)", {"codigo": "NASCIDOS_VIVOS"}),
    ("Total de óbitos (SIM)", {"codigo": "OBITOS_TOTAL"}),
)


# =========================================================================
# Serviço
# =========================================================================
class ServicoIndicadores:
    def __init__(self, repositorio: Repositorio) -> None:
        self._repo = repositorio

    # ------------------------------------------------------ RN07
    @staticmethod
    def variacao_percentual(atual: float, anterior: float) -> float | None:
        """(atual − anterior) ÷ anterior × 100, uma casa decimal; anterior 0 → None."""
        if anterior == 0:
            return None
        return round((atual - anterior) / anterior * 100, 1)

    @staticmethod
    def formatar_variacao(variacao: float | None) -> str:
        if variacao is None:
            return "—"
        return f"{variacao:+.1f}%".replace(".", ",")

    # ------------------------------------------------------ RF07
    def filtrar_indicadores(
        self,
        modulo: str | None = None,
        grupo: str | None = None,
        codigo: str | None = None,
    ) -> list[Indicador]:
        """Filtro por sistema de origem, grupo epidemiológico e agravo."""
        indicadores = self._repo.listar_indicadores()
        if modulo:
            indicadores = [i for i in indicadores if i.modulo.sigla == modulo.upper()]
        if grupo:
            indicadores = [i for i in indicadores if i.grupo.lower() == grupo.lower()]
        if codigo:
            indicadores = [i for i in indicadores if i.codigo == codigo.upper()]
        return indicadores

    def grupos(self, modulo: str | None = None) -> list[str]:
        return sorted({i.grupo for i in self.filtrar_indicadores(modulo=modulo)})

    # ---------------------------------------------------- RN06 / RF13
    def total(self, indicadores: Iterable[Indicador], periodo: Periodo) -> float:
        codigos = {i.codigo for i in indicadores}
        return sum(
            l.valor
            for l in self._repo.lancamentos()
            if l.indicador.codigo in codigos and periodo.contem(l.ano, l.mes)
        )

    def total_indicador(self, codigo: str, periodo: Periodo) -> float:
        return self.total([self._repo.buscar_indicador(codigo)], periodo)

    def valores_mensais(self, indicador: Indicador, periodo: Periodo) -> dict[int, float]:
        """Valor de cada mês do período (0 quando não houver lançamento)."""
        valores = {mes: 0 for mes in periodo.meses}
        for l in self._repo.lancamentos():
            if l.indicador.codigo == indicador.codigo and periodo.contem(l.ano, l.mes):
                valores[l.mes] = l.valor
        return valores

    def serie_mensal(self, indicadores: Iterable[Indicador], periodo: Periodo) -> dict[str, float]:
        indicadores = list(indicadores)
        return {
            NOMES_MESES[mes - 1]: self.total(indicadores, Periodo.mes(periodo.ano, mes))
            for mes in periodo.meses
        }

    def ranking(self, indicadores: Iterable[Indicador], periodo: Periodo, limite: int = 5) -> list[tuple[str, float]]:
        totais = [(i.nome, self.total([i], periodo)) for i in indicadores]
        totais = [t for t in totais if t[1] > 0]
        return sorted(totais, key=lambda t: t[1], reverse=True)[:limite]

    # ------------------------------------------------------ RF06
    def comparar(
        self,
        usuario: Usuario,
        periodo_atual: Periodo,
        periodo_base: Periodo,
        modulo: str | None = None,
        grupo: str | None = None,
        codigo: str | None = None,
    ) -> list[LinhaComparativo]:
        """Compara dois períodos do MESMO tipo (RN10)."""
        exigir_permissao(usuario, Permissao.VER_PAINEL)
        if periodo_atual.tipo != periodo_base.tipo:
            raise ErroValidacao("Só é possível comparar períodos do mesmo tipo (RN10).")
        linhas = []
        for indicador in self.filtrar_indicadores(modulo, grupo, codigo):
            atual = self.total([indicador], periodo_atual)
            base = self.total([indicador], periodo_base)
            if atual == 0 and base == 0:
                continue
            linhas.append(
                LinhaComparativo(
                    indicador.codigo, indicador.nome, atual, base,
                    atual - base, self.variacao_percentual(atual, base),
                )
            )
        return linhas

    # ------------------------------------------------------ RF05
    def ultimo_quadrimestre_com_dados(self) -> Periodo | None:
        lancamentos = self._repo.lancamentos()
        if not lancamentos:
            return None
        ultimo = max(lancamentos, key=lambda l: (l.ano, l.mes))
        return Periodo.quadrimestre(ultimo.ano, quadrimestre_do_mes(ultimo.mes))

    def painel(self, usuario: Usuario, periodo: Periodo | None = None) -> ResumoPainel:
        """Painel principal: por padrão, o último quadrimestre com dados (CA de RF05)."""
        exigir_permissao(usuario, Permissao.VER_PAINEL)
        periodo = periodo or self.ultimo_quadrimestre_com_dados()
        if periodo is None:
            raise ErroValidacao("Ainda não há lançamentos para montar o painel.")
        anterior = periodo.mesmo_periodo_ano_anterior()
        resumo = ResumoPainel(periodo)

        for titulo, filtro in CARTOES_PAINEL:
            indicadores = self.filtrar_indicadores(**filtro)
            if not indicadores:
                continue
            atual = self.total(indicadores, periodo)
            base = self.total(indicadores, anterior)
            if atual == 0 and base == 0:
                continue  # sem dados no período: não mostra cartão zerado
            resumo.cartoes.append(
                Cartao(titulo, atual, base, self.variacao_percentual(atual, base))
            )

        ciclos = [c for c in self._repo.ciclos_pncd() if periodo.contem(c.ano, c.mes_referencia)]
        if ciclos:
            resumo.cartoes.append(Cartao("Cobertura PNCD (último ciclo)", f"{ciclos[-1].cobertura():.2f}%".replace(".", ",")))
        lirass = [l for l in self._repo.levantamentos_liraa() if periodo.contem(l.ano, l.mes_referencia)]
        if lirass:
            ultimo = lirass[-1]
            resumo.cartoes.append(
                Cartao("LIRAa (IIP)", f"{ultimo.indice_predial:.1f}".replace(".", ",") + f" – {ultimo.classificar_risco()}")
            )

        sinan = self.filtrar_indicadores(modulo="SINAN")
        resumo.principais_agravos = self.ranking(sinan, periodo)
        resumo.serie_mensal = self.serie_mensal(sinan, periodo)
        return resumo
