"""Registros epidemiológicos: abstração, herança e polimorfismo (alteração A01).

RegistroEpidemiologico (classe abstrata)
├── LancamentoMensal   → total mensal de um indicador (RF01, RF02, RF04)
├── CicloPNCD          → cobertura de imóveis por ciclo (RF03, RN08)
└── LevantamentoLIRAa  → índices de infestação e risco (RF03, RN09)

As três subclasses são usadas pela mesma interface:
- validar(hoje)  → aplica as regras de entrada de cada tipo (RF12)
- resultado()    → devolve o indicador calculado de cada tipo (RF13)
- chave()        → identifica o registro único (RN04)
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date, datetime
from numbers import Real
from typing import TYPE_CHECKING

from ..excecoes import ErroValidacao
from .enums import OrigemDado, TipoValor

if TYPE_CHECKING:
    from .indicador import Indicador
    from .modulo import Modulo
    from .usuario import Usuario


def _numero_valido(valor: object) -> bool:
    """True para int/float (bool não conta como número aqui)."""
    return isinstance(valor, Real) and not isinstance(valor, bool)


def quadrimestre_do_mes(mes: int) -> int:
    """RN10: 1º = jan.–abr.; 2º = mai.–ago.; 3º = set.–dez."""
    if not 1 <= mes <= 12:
        raise ErroValidacao("O mês deve estar entre 1 e 12.")
    return (mes - 1) // 4 + 1


# =========================================================================
# Classe abstrata
# =========================================================================
class RegistroEpidemiologico(ABC):
    """Contrato comum a todo dado lançado no sistema."""

    def __init__(
        self,
        ano: int,
        registrado_por: "Usuario | None" = None,
        id: int | None = None,
        criado_em: datetime | None = None,
    ) -> None:
        self.id = id
        self.ano = ano
        self.registrado_por = registrado_por  # associação Usuario "registra"
        self.criado_em = criado_em or datetime.now()

    @property
    def ano(self) -> int:
        return self._ano

    @ano.setter
    def ano(self, valor: int) -> None:
        if not isinstance(valor, int) or isinstance(valor, bool) or not 2000 <= valor <= 2100:
            raise ErroValidacao("Ano inválido (use um ano entre 2000 e 2100).")
        self._ano = valor

    # ---- métodos abstratos: cada subclasse é obrigada a implementar
    @abstractmethod
    def validar(self, hoje: date | None = None) -> bool:
        """Verifica as regras de entrada; lança ErroValidacao se algo estiver errado."""

    @abstractmethod
    def resultado(self) -> object:
        """Indicador calculado a partir do registro."""

    @abstractmethod
    def chave(self) -> tuple:
        """Identificação única do registro (RN04)."""

    @property
    @abstractmethod
    def mes_referencia(self) -> int:
        """Mês usado para posicionar o registro no quadrimestre."""

    # ---- métodos concretos herdados pelas três subclasses
    @property
    def quadrimestre(self) -> int:
        return quadrimestre_do_mes(self.mes_referencia)

    def pertence_ao_quadrimestre(self, ano: int, quadrimestre: int) -> bool:
        return self.ano == ano and self.quadrimestre == quadrimestre

    @staticmethod
    def _mes_encerrado(ano: int, mes: int, hoje: date) -> bool:
        """RN05: só se lançam meses já encerrados."""
        return (ano, mes) < (hoje.year, hoje.month)

    def __eq__(self, outro: object) -> bool:
        """Dois registros são o mesmo se têm a mesma chave (base da RN04)."""
        if not isinstance(outro, RegistroEpidemiologico):
            return NotImplemented
        return self.chave() == outro.chave()

    def __hash__(self) -> int:
        return hash(self.chave())


# =========================================================================
# Subclasse 1 – lançamento mensal
# =========================================================================
class LancamentoMensal(RegistroEpidemiologico):
    """Total mensal de um indicador (ex.: Dengue = 418 em 05/2026)."""

    def __init__(
        self,
        indicador: "Indicador",
        ano: int,
        mes: int,
        valor: float,
        origem: OrigemDado = OrigemDado.DIGITACAO,
        registrado_por: "Usuario | None" = None,
        importacao_id: int | None = None,
        id: int | None = None,
        criado_em: datetime | None = None,
    ) -> None:
        self._indicador = indicador  # associação Indicador 1 — * LancamentoMensal (A02)
        super().__init__(ano, registrado_por, id, criado_em)
        self.mes = mes
        self.valor = valor
        self.origem = OrigemDado(origem)
        self.importacao_id = importacao_id  # associação Importacao "origina"

    @property
    def indicador(self) -> "Indicador":
        return self._indicador

    @property
    def mes(self) -> int:
        return self._mes

    @mes.setter
    def mes(self, valor: int) -> None:
        if not isinstance(valor, int) or isinstance(valor, bool) or not 1 <= valor <= 12:
            raise ErroValidacao("O mês deve ser um número inteiro de 1 a 12.")
        self._mes = valor

    @property
    def valor(self) -> float:
        return self._valor

    @valor.setter
    def valor(self, novo: float) -> None:
        """RN05 / A08: número ≥ 0; inteiro se o indicador for do tipo INTEIRO."""
        if not _numero_valido(novo):
            raise ErroValidacao("O valor deve ser numérico.")
        if novo < 0:
            raise ErroValidacao("O valor não pode ser negativo.")
        if self.indicador.tipo_valor is TipoValor.INTEIRO:
            if isinstance(novo, float):
                if not novo.is_integer():
                    raise ErroValidacao(
                        f"{self.indicador.nome} aceita apenas números inteiros."
                    )
                novo = int(novo)
        self._valor = novo

    @property
    def mes_referencia(self) -> int:
        return self.mes

    def validar(self, hoje: date | None = None) -> bool:
        hoje = hoje or date.today()
        if not self.indicador.ativo:
            raise ErroValidacao(f"O indicador {self.indicador.nome} está inativo.")
        if not self._mes_encerrado(self.ano, self.mes, hoje):
            raise ErroValidacao(
                f"{self.mes:02d}/{self.ano} ainda não terminou: só é possível lançar meses encerrados."
            )
        return True

    def resultado(self) -> float:
        return self.valor

    def chave(self) -> tuple:
        return ("LANCAMENTO", self.indicador.codigo, self.ano, self.mes)

    def __str__(self) -> str:
        return f"{self.indicador.nome} – {self.mes:02d}/{self.ano}: {self.valor}"

    def __repr__(self) -> str:
        return (
            f"LancamentoMensal(indicador={self.indicador.codigo!r}, ano={self.ano}, "
            f"mes={self.mes}, valor={self.valor!r})"
        )


# =========================================================================
# Subclasse 2 – ciclo do PNCD
# =========================================================================
class CicloPNCD(RegistroEpidemiologico):
    """Ciclo bimestral de visitas a imóveis (ex.: 40.100 de 40.680 = 98,57%)."""

    def __init__(
        self,
        modulo: "Modulo",
        ano: int,
        numero: int,
        mes_inicial: int,
        imoveis_programados: int,
        imoveis_trabalhados: int,
        registrado_por: "Usuario | None" = None,
        id: int | None = None,
        criado_em: datetime | None = None,
    ) -> None:
        self.modulo = modulo  # associação Modulo (Endemias) 1 — * CicloPNCD
        super().__init__(ano, registrado_por, id, criado_em)
        self.numero = numero
        self.mes_inicial = mes_inicial
        self.imoveis_programados = imoveis_programados
        self.imoveis_trabalhados = imoveis_trabalhados

    @property
    def numero(self) -> int:
        return self._numero

    @numero.setter
    def numero(self, valor: int) -> None:
        if not isinstance(valor, int) or not 1 <= valor <= 6:
            raise ErroValidacao("O número do ciclo deve ser de 1 a 6 (ciclos bimestrais).")
        self._numero = valor

    @property
    def mes_inicial(self) -> int:
        return self._mes_inicial

    @mes_inicial.setter
    def mes_inicial(self, valor: int) -> None:
        if not isinstance(valor, int) or not 1 <= valor <= 11:
            raise ErroValidacao("O ciclo é bimestral: o mês inicial deve ser de 1 a 11.")
        self._mes_inicial = valor

    @property
    def mes_final(self) -> int:
        """Ciclo bimestral: termina no mês seguinte ao inicial."""
        return self.mes_inicial + 1

    @property
    def imoveis_programados(self) -> int:
        return self._programados

    @imoveis_programados.setter
    def imoveis_programados(self, valor: int) -> None:
        if not isinstance(valor, int) or valor <= 0:
            raise ErroValidacao("Imóveis programados deve ser um inteiro maior que zero.")
        if hasattr(self, "_trabalhados") and self._trabalhados > valor:
            raise ErroValidacao("Imóveis programados não pode ficar menor que os trabalhados.")
        self._programados = valor

    @property
    def imoveis_trabalhados(self) -> int:
        return self._trabalhados

    @imoveis_trabalhados.setter
    def imoveis_trabalhados(self, valor: int) -> None:
        if not isinstance(valor, int) or valor < 0:
            raise ErroValidacao("Imóveis trabalhados deve ser um inteiro ≥ 0.")
        if valor > self.imoveis_programados:
            raise ErroValidacao(
                "Imóveis trabalhados não pode ser maior que os programados."
            )
        self._trabalhados = valor

    @property
    def mes_referencia(self) -> int:
        return self.mes_final

    def cobertura(self) -> float:
        """RN08: trabalhados ÷ programados × 100, com duas casas decimais."""
        return round(self.imoveis_trabalhados / self.imoveis_programados * 100, 2)

    def validar(self, hoje: date | None = None) -> bool:
        hoje = hoje or date.today()
        if not self._mes_encerrado(self.ano, self.mes_final, hoje):
            raise ErroValidacao("O ciclo ainda não terminou: só é possível lançar ciclos encerrados.")
        return True

    def resultado(self) -> float:
        return self.cobertura()

    def chave(self) -> tuple:
        return ("PNCD", self.ano, self.numero)

    def __str__(self) -> str:
        return (
            f"Ciclo {self.numero}/{self.ano} ({self.mes_inicial:02d}–{self.mes_final:02d}): "
            f"{self.imoveis_trabalhados}/{self.imoveis_programados} imóveis – "
            + f"{self.cobertura():.2f}%".replace(".", ",")
        )

    def __repr__(self) -> str:
        return (
            f"CicloPNCD(ano={self.ano}, numero={self.numero}, mes_inicial={self.mes_inicial}, "
            f"programados={self.imoveis_programados}, trabalhados={self.imoveis_trabalhados})"
        )


# =========================================================================
# Subclasse 3 – LIRAa
# =========================================================================
class LevantamentoLIRAa(RegistroEpidemiologico):
    """Levantamento de Índice Rápido para Aedes aegypti (ex.: IIP 0,2 → satisfatório)."""

    SATISFATORIO = "satisfatório"
    ALERTA = "alerta"
    RISCO = "risco"

    def __init__(
        self,
        modulo: "Modulo",
        data_inicio: date,
        data_fim: date,
        indice_predial: float,
        indice_breteau: float,
        pontos_estrategicos: int = 0,
        registrado_por: "Usuario | None" = None,
        id: int | None = None,
        criado_em: datetime | None = None,
    ) -> None:
        if not isinstance(data_inicio, date) or not isinstance(data_fim, date):
            raise ErroValidacao("As datas do LIRAa são obrigatórias.")
        if data_fim < data_inicio:
            raise ErroValidacao("A data final do LIRAa não pode ser anterior à inicial.")
        self.modulo = modulo  # associação Modulo (Endemias) 1 — * LevantamentoLIRAa
        self._data_inicio = data_inicio
        self._data_fim = data_fim
        super().__init__(data_fim.year, registrado_por, id, criado_em)
        self.indice_predial = indice_predial
        self.indice_breteau = indice_breteau
        self.pontos_estrategicos = pontos_estrategicos

    @property
    def data_inicio(self) -> date:
        return self._data_inicio

    @property
    def data_fim(self) -> date:
        return self._data_fim

    @property
    def indice_predial(self) -> float:
        return self._iip

    @indice_predial.setter
    def indice_predial(self, valor: float) -> None:
        if not _numero_valido(valor) or valor < 0:
            raise ErroValidacao("O Índice de Infestação Predial deve ser um número ≥ 0.")
        self._iip = float(valor)

    @property
    def indice_breteau(self) -> float:
        return self._ib

    @indice_breteau.setter
    def indice_breteau(self, valor: float) -> None:
        if not _numero_valido(valor) or valor < 0:
            raise ErroValidacao("O Índice de Breteau deve ser um número ≥ 0.")
        self._ib = float(valor)

    @property
    def pontos_estrategicos(self) -> int:
        return self._pontos

    @pontos_estrategicos.setter
    def pontos_estrategicos(self, valor: int) -> None:
        if not isinstance(valor, int) or isinstance(valor, bool) or valor < 0:
            raise ErroValidacao("Pontos estratégicos deve ser um inteiro ≥ 0.")
        self._pontos = valor

    @property
    def mes_referencia(self) -> int:
        return self.data_fim.month

    def classificar_risco(self) -> str:
        """RN09: IIP < 1% satisfatório; 1% a 3,9% alerta; ≥ 4% risco (BRASIL, 2009)."""
        if self.indice_predial < 1:
            return self.SATISFATORIO
        if self.indice_predial < 4:
            return self.ALERTA
        return self.RISCO

    def validar(self, hoje: date | None = None) -> bool:
        hoje = hoje or date.today()
        if self.data_fim >= hoje:
            raise ErroValidacao("O LIRAa ainda não terminou: só é possível lançar levantamentos encerrados.")
        return True

    def resultado(self) -> str:
        return self.classificar_risco()

    def chave(self) -> tuple:
        return ("LIRAA", self.data_inicio.isoformat())

    def __str__(self) -> str:
        return (
            f"LIRAa {self.data_inicio:%d/%m/%Y}–{self.data_fim:%d/%m/%Y}: "
            f"IIP {self.indice_predial:.1f} / IB {self.indice_breteau:.1f}".replace(".", ",")
            + f" – {self.classificar_risco()}"
        )

    def __repr__(self) -> str:
        return (
            f"LevantamentoLIRAa(data_inicio={self.data_inicio!r}, data_fim={self.data_fim!r}, "
            f"iip={self.indice_predial}, ib={self.indice_breteau})"
        )
