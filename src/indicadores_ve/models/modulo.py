"""Classe Modulo (Diagrama de Classes – TED 03).

Os módulos são os sistemas de origem dos dados: SINAN, LACEN, Endemias
e SIM/SINASC (RF07 – filtro por sistema de origem).

Relacionamento de COMPOSIÇÃO Modulo ◆— Indicador:
- o módulo cria os seus indicadores (adicionar_indicador);
- os indicadores ficam guardados só dentro do módulo;
- se o módulo deixa de existir, os indicadores deixam de existir junto.
"""

from __future__ import annotations

from ..excecoes import ErroValidacao, RegistroDuplicado, RegistroNaoEncontrado
from .enums import Periodicidade, TipoValor
from .indicador import Indicador


class Modulo:
    """Sistema de origem dos indicadores."""

    def __init__(self, sigla: str, nome: str, id: int | None = None) -> None:
        self.id = id
        self.sigla = sigla
        self.nome = nome
        self._indicadores: dict[str, Indicador] = {}

    # ----------------------------------------------------------- propriedades
    @property
    def sigla(self) -> str:
        return self._sigla

    @sigla.setter
    def sigla(self, valor: str) -> None:
        valor = (valor or "").strip().upper()
        if not valor:
            raise ErroValidacao("A sigla do módulo é obrigatória.")
        self._sigla = valor

    @property
    def nome(self) -> str:
        return self._nome

    @nome.setter
    def nome(self, valor: str) -> None:
        valor = (valor or "").strip()
        if not valor:
            raise ErroValidacao("O nome do módulo é obrigatório.")
        self._nome = valor

    @property
    def indicadores(self) -> tuple[Indicador, ...]:
        """Cópia somente leitura: a lista interna só muda pelos métodos do módulo."""
        return tuple(self._indicadores.values())

    # ------------------------------------------------------ composição
    def adicionar_indicador(
        self,
        codigo: str,
        nome: str,
        grupo: str,
        tipo_valor: TipoValor = TipoValor.INTEIRO,
        periodicidade: Periodicidade = Periodicidade.MENSAL,
        ativo: bool = True,
        id: int | None = None,
    ) -> Indicador:
        """Cria um indicador dentro do módulo (RNF08: novo agravo/exame por cadastro)."""
        indicador = Indicador(self, codigo, nome, grupo, tipo_valor, periodicidade, ativo, id)
        if indicador.codigo in self._indicadores:
            raise RegistroDuplicado(
                f"O indicador {indicador.codigo} já existe no módulo {self.sigla}."
            )
        self._indicadores[indicador.codigo] = indicador
        return indicador

    def obter_indicador(self, codigo: str) -> Indicador:
        codigo = (codigo or "").strip().upper()
        try:
            return self._indicadores[codigo]
        except KeyError:
            raise RegistroNaoEncontrado(
                f"Indicador {codigo} não encontrado no módulo {self.sigla}."
            ) from None

    def remover_indicador(self, codigo: str) -> None:
        indicador = self.obter_indicador(codigo)
        del self._indicadores[indicador.codigo]

    def indicadores_do_grupo(self, grupo: str) -> list[Indicador]:
        return [i for i in self._indicadores.values() if i.grupo.lower() == grupo.lower()]

    # ---------------------------------------------------- métodos especiais
    def __len__(self) -> int:
        """len(modulo) = quantidade de indicadores cadastrados."""
        return len(self._indicadores)

    def __contains__(self, codigo: object) -> bool:
        """Permite escrever: 'DENGUE' in modulo_sinan."""
        return isinstance(codigo, str) and codigo.strip().upper() in self._indicadores

    def __str__(self) -> str:
        return f"{self.sigla} – {self.nome}"

    def __repr__(self) -> str:
        return f"Modulo(sigla={self.sigla!r}, nome={self.nome!r}, indicadores={len(self)})"
