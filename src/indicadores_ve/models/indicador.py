"""Classe Indicador (Diagrama de Classes – TED 03).

Um indicador é cada linha dos relatórios da VE: um agravo do SINAN
(ex.: Dengue), um tipo de exame do LACEN (ex.: Tuberculose TRM) ou um
dado vital (ex.: Nascidos vivos).

Composição: todo Indicador pertence a um Modulo e é criado por ele
(ver Modulo.adicionar_indicador). Por isso o construtor exige o módulo.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..excecoes import ErroValidacao
from .enums import Periodicidade, TipoValor

if TYPE_CHECKING:  # evita importação circular; usado só para dicas de tipo
    from .modulo import Modulo


class Indicador:
    """Indicador epidemiológico cadastrado em um módulo."""

    def __init__(
        self,
        modulo: "Modulo",
        codigo: str,
        nome: str,
        grupo: str,
        tipo_valor: TipoValor = TipoValor.INTEIRO,
        periodicidade: Periodicidade = Periodicidade.MENSAL,
        ativo: bool = True,
        id: int | None = None,
    ) -> None:
        self._modulo = modulo
        self.id = id
        self.codigo = codigo
        self.nome = nome
        self.grupo = grupo
        self._tipo_valor = TipoValor(tipo_valor)
        self._periodicidade = Periodicidade(periodicidade)
        self._ativo = bool(ativo)

    # ----------------------------------------------------------- propriedades
    @property
    def modulo(self) -> "Modulo":
        """Módulo dono do indicador (somente leitura: composição)."""
        return self._modulo

    @property
    def codigo(self) -> str:
        return self._codigo

    @codigo.setter
    def codigo(self, valor: str) -> None:
        valor = (valor or "").strip().upper()
        if not valor:
            raise ErroValidacao("O código do indicador é obrigatório.")
        if " " in valor:
            raise ErroValidacao("O código do indicador não pode ter espaços.")
        self._codigo = valor

    @property
    def nome(self) -> str:
        return self._nome

    @nome.setter
    def nome(self, valor: str) -> None:
        valor = (valor or "").strip()
        if not valor:
            raise ErroValidacao("O nome do indicador é obrigatório.")
        self._nome = valor

    @property
    def grupo(self) -> str:
        """Grupo epidemiológico usado nos filtros (RF07), ex.: 'Arboviroses'."""
        return self._grupo

    @grupo.setter
    def grupo(self, valor: str) -> None:
        valor = (valor or "").strip()
        if not valor:
            raise ErroValidacao("O grupo do indicador é obrigatório.")
        self._grupo = valor

    @property
    def tipo_valor(self) -> TipoValor:
        return self._tipo_valor

    @property
    def periodicidade(self) -> Periodicidade:
        return self._periodicidade

    @property
    def ativo(self) -> bool:
        return self._ativo

    # --------------------------------------------------------------- métodos
    def ativar(self) -> None:
        self._ativo = True

    def inativar(self) -> None:
        """Inativa sem apagar: o histórico de lançamentos continua válido (RNF08)."""
        self._ativo = False

    # ---------------------------------------------------- métodos especiais
    def __str__(self) -> str:
        return f"{self.nome} ({self.modulo.sigla})"

    def __repr__(self) -> str:
        return (
            f"Indicador(codigo={self.codigo!r}, nome={self.nome!r}, "
            f"modulo={self.modulo.sigla!r}, grupo={self.grupo!r})"
        )
