"""Contrato de persistência (abstração) e implementação em memória.

Repositorio (classe abstrata)
├── RepositorioMemoria  → usado nos testes (não grava nada em disco)
└── RepositorioJSON     → grava em data/banco.json (persistence/repositorio_json.py)

Os serviços só conhecem a interface Repositorio. Assim, trocar JSON por
banco relacional no futuro não muda nenhuma regra de negócio (alteração A04).

A classe base guarda os objetos em memória e oferece as operações de
cadastrar, consultar, atualizar e excluir. As subclasses só decidem COMO
carregar() e salvar() esse estado.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterable

from ..excecoes import RegistroDuplicado, RegistroNaoEncontrado
from ..models import (
    CicloPNCD,
    Importacao,
    Indicador,
    LancamentoMensal,
    LevantamentoLIRAa,
    LogAuditoria,
    Modulo,
    Perfil,
    RegistroEpidemiologico,
    RelatorioQuadrimestral,
    Usuario,
)


class Repositorio(ABC):
    """Estado do sistema + operações de acesso aos dados."""

    def __init__(self) -> None:
        self.limpar()

    def limpar(self) -> None:
        self._modulos: dict[str, Modulo] = {}
        self._perfis: dict[str, Perfil] = {}
        self._usuarios: dict[str, Usuario] = {}
        self._registros: dict[tuple, RegistroEpidemiologico] = {}
        self._relatorios: dict[tuple[int, int], RelatorioQuadrimestral] = {}
        self._importacoes: dict[int, Importacao] = {}
        self._logs: list[LogAuditoria] = []
        self._contadores: dict[str, int] = {}

    # ------------------------------------------------- contrato abstrato
    @abstractmethod
    def carregar(self) -> None:
        """Lê o estado salvo para a memória."""

    @abstractmethod
    def salvar(self) -> None:
        """Grava o estado da memória."""

    # ----------------------------------------------------------- ids
    def proximo_id(self, colecao: str) -> int:
        self._contadores[colecao] = self._contadores.get(colecao, 0) + 1
        return self._contadores[colecao]

    def _ajustar_contador(self, colecao: str, id_existente: int | None) -> None:
        if id_existente is not None:
            self._contadores[colecao] = max(self._contadores.get(colecao, 0), id_existente)

    # ------------------------------------------------------- módulos
    def adicionar_modulo(self, modulo: Modulo) -> Modulo:
        if modulo.sigla in self._modulos:
            raise RegistroDuplicado(f"O módulo {modulo.sigla} já existe.")
        if modulo.id is None:
            modulo.id = self.proximo_id("modulos")
        self._ajustar_contador("modulos", modulo.id)
        self._modulos[modulo.sigla] = modulo
        return modulo

    def obter_modulo(self, sigla: str) -> Modulo:
        try:
            return self._modulos[(sigla or "").strip().upper()]
        except KeyError:
            raise RegistroNaoEncontrado(f"Módulo {sigla} não encontrado.") from None

    def listar_modulos(self) -> list[Modulo]:
        return list(self._modulos.values())

    def buscar_indicador(self, codigo: str, sigla_modulo: str | None = None) -> Indicador:
        """Procura o indicador pelo código (opcionalmente só num módulo)."""
        modulos = [self.obter_modulo(sigla_modulo)] if sigla_modulo else self._modulos.values()
        for modulo in modulos:
            if codigo in modulo:
                return modulo.obter_indicador(codigo)
        raise RegistroNaoEncontrado(f"Indicador {codigo} não encontrado.")

    def listar_indicadores(self) -> list[Indicador]:
        return [i for m in self._modulos.values() for i in m.indicadores]

    # -------------------------------------------------- perfis e usuários
    def adicionar_perfil(self, perfil: Perfil) -> Perfil:
        if perfil.nome in self._perfis:
            raise RegistroDuplicado(f"O perfil {perfil.nome} já existe.")
        if perfil.id is None:
            perfil.id = self.proximo_id("perfis")
        self._ajustar_contador("perfis", perfil.id)
        self._perfis[perfil.nome] = perfil
        return perfil

    def obter_perfil(self, nome: str) -> Perfil:
        try:
            return self._perfis[nome]
        except KeyError:
            raise RegistroNaoEncontrado(f"Perfil {nome} não encontrado.") from None

    def listar_perfis(self) -> list[Perfil]:
        return list(self._perfis.values())

    def adicionar_usuario(self, usuario: Usuario) -> Usuario:
        if usuario.login in self._usuarios:
            raise RegistroDuplicado(f"O login {usuario.login} já está em uso.")
        if usuario.id is None:
            usuario.id = self.proximo_id("usuarios")
        self._ajustar_contador("usuarios", usuario.id)
        self._usuarios[usuario.login] = usuario
        return usuario

    def obter_usuario(self, login: str) -> Usuario:
        try:
            return self._usuarios[(login or "").strip().lower()]
        except KeyError:
            raise RegistroNaoEncontrado(f"Usuário {login} não encontrado.") from None

    def listar_usuarios(self) -> list[Usuario]:
        return list(self._usuarios.values())

    # ------------------------------------------------------- registros
    def salvar_registro(self, registro: RegistroEpidemiologico) -> RegistroEpidemiologico:
        """Inclui ou substitui (a decisão de substituir fica no serviço – RN04)."""
        anterior = self._registros.get(registro.chave())
        if registro.id is None:
            registro.id = anterior.id if anterior else self.proximo_id("registros")
        self._ajustar_contador("registros", registro.id)
        self._registros[registro.chave()] = registro
        return registro

    def obter_registro(self, chave: tuple) -> RegistroEpidemiologico | None:
        return self._registros.get(tuple(chave))

    def remover_registro(self, chave: tuple) -> RegistroEpidemiologico:
        try:
            return self._registros.pop(tuple(chave))
        except KeyError:
            raise RegistroNaoEncontrado("Registro não encontrado.") from None

    def listar_registros(self, tipo: type | None = None) -> list[RegistroEpidemiologico]:
        registros = self._registros.values()
        if tipo is not None:
            registros = [r for r in registros if isinstance(r, tipo)]
        return list(registros)

    def lancamentos(self) -> list[LancamentoMensal]:
        return self.listar_registros(LancamentoMensal)

    def ciclos_pncd(self) -> list[CicloPNCD]:
        return sorted(self.listar_registros(CicloPNCD), key=lambda c: (c.ano, c.numero))

    def levantamentos_liraa(self) -> list[LevantamentoLIRAa]:
        return sorted(self.listar_registros(LevantamentoLIRAa), key=lambda l: l.data_inicio)

    # ------------------------------------------------------ relatórios
    def obter_relatorio(self, ano: int, quadrimestre: int) -> RelatorioQuadrimestral | None:
        return self._relatorios.get((ano, quadrimestre))

    def salvar_relatorio(self, relatorio: RelatorioQuadrimestral) -> RelatorioQuadrimestral:
        if relatorio.id is None:
            relatorio.id = self.proximo_id("relatorios")
        self._ajustar_contador("relatorios", relatorio.id)
        self._relatorios[(relatorio.ano, relatorio.quadrimestre)] = relatorio
        return relatorio

    def listar_relatorios(self) -> list[RelatorioQuadrimestral]:
        return sorted(self._relatorios.values(), key=lambda r: (r.ano, r.quadrimestre))

    # ----------------------------------------------------- importações
    def salvar_importacao(self, importacao: Importacao) -> Importacao:
        if importacao.id is None:
            importacao.id = self.proximo_id("importacoes")
        self._ajustar_contador("importacoes", importacao.id)
        self._importacoes[importacao.id] = importacao
        return importacao

    def obter_importacao(self, id: int) -> Importacao:
        try:
            return self._importacoes[id]
        except KeyError:
            raise RegistroNaoEncontrado(f"Importação {id} não encontrada.") from None

    def listar_importacoes(self) -> list[Importacao]:
        return list(self._importacoes.values())

    # -------------------------------------------------------- auditoria
    def adicionar_log(self, log: LogAuditoria) -> LogAuditoria:
        self._logs.append(log)
        return log

    def listar_logs(self) -> list[LogAuditoria]:
        return list(self._logs)

    def carregar_logs(self, logs: Iterable[LogAuditoria]) -> None:
        self._logs = list(logs)


class RepositorioMemoria(Repositorio):
    """Mantém tudo só na memória. Usado nos testes automatizados."""

    def carregar(self) -> None:  # nada a carregar
        pass

    def salvar(self) -> None:  # nada a gravar
        pass
