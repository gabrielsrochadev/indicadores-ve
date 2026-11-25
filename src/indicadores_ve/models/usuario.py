"""Classes Usuario, Perfil e Permissao (Diagrama de Classes – TED 03).

- Usuario → Perfil: associação (cada usuário tem um perfil).
- Perfil ◇— Permissao: AGREGAÇÃO. As permissões existem por conta própria e
  podem ser compartilhadas por vários perfis (o Coordenador tem as mesmas
  permissões do Gestor e mais a de homologar).

Segurança (RNF05): a senha nunca é guardada em texto claro. Guardamos só o
hash PBKDF2-SHA256 com "sal" aleatório (biblioteca padrão hashlib).
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime
from typing import Iterable

from ..excecoes import ErroValidacao


class Permissao:
    """Ação que um perfil pode executar (RN03)."""

    # Códigos usados pelo sistema
    LANCAR_DADOS = "lancar_dados"
    IMPORTAR_PLANILHA = "importar_planilha"
    VER_PAINEL = "ver_painel"
    EXPORTAR_RELATORIO = "exportar_relatorio"
    HOMOLOGAR_RELATORIO = "homologar_relatorio"
    GERENCIAR_USUARIOS = "gerenciar_usuarios"

    def __init__(self, codigo: str, descricao: str = "") -> None:
        codigo = (codigo or "").strip().lower()
        if not codigo:
            raise ErroValidacao("O código da permissão é obrigatório.")
        self._codigo = codigo
        self.descricao = descricao

    @property
    def codigo(self) -> str:
        return self._codigo

    def __eq__(self, outro: object) -> bool:
        if not isinstance(outro, Permissao):
            return NotImplemented
        return self.codigo == outro.codigo

    def __hash__(self) -> int:
        return hash(self.codigo)

    def __str__(self) -> str:
        return self.descricao or self.codigo

    def __repr__(self) -> str:
        return f"Permissao(codigo={self.codigo!r})"


class Perfil:
    """Perfil de acesso: Digitador, Coordenador, Gestor ou Administrador (SRS seção 6)."""

    def __init__(
        self,
        nome: str,
        descricao: str = "",
        permissoes: Iterable[Permissao] = (),
        id: int | None = None,
    ) -> None:
        nome = (nome or "").strip()
        if not nome:
            raise ErroValidacao("O nome do perfil é obrigatório.")
        self.id = id
        self.nome = nome
        self.descricao = descricao
        self._permissoes: set[Permissao] = set()
        for permissao in permissoes:
            self.adicionar_permissao(permissao)

    @property
    def permissoes(self) -> frozenset[Permissao]:
        """Somente leitura: alterações passam por adicionar/remover."""
        return frozenset(self._permissoes)

    def adicionar_permissao(self, permissao: Permissao) -> None:
        if not isinstance(permissao, Permissao):
            raise ErroValidacao("Só é possível adicionar objetos Permissao a um perfil.")
        self._permissoes.add(permissao)

    def remover_permissao(self, permissao: Permissao) -> None:
        self._permissoes.discard(permissao)

    def possui(self, codigo: str) -> bool:
        return any(p.codigo == codigo for p in self._permissoes)

    def __contains__(self, codigo: object) -> bool:
        """Permite escrever: Permissao.VER_PAINEL in perfil."""
        return isinstance(codigo, str) and self.possui(codigo)

    def __str__(self) -> str:
        return self.nome

    def __repr__(self) -> str:
        codigos = sorted(p.codigo for p in self._permissoes)
        return f"Perfil(nome={self.nome!r}, permissoes={codigos})"


class Usuario:
    """Usuário do sistema com login individual (RF09, RF10, RNF05)."""

    TAMANHO_MINIMO_SENHA = 8
    _ITERACOES_HASH = 100_000

    def __init__(
        self,
        nome: str,
        login: str,
        perfil: Perfil,
        senha: str | None = None,
        senha_hash: str | None = None,
        ativo: bool = True,
        ultimo_acesso: datetime | None = None,
        id: int | None = None,
    ) -> None:
        self.id = id
        self.nome = nome
        self.login = login
        self.perfil = perfil
        self._ativo = bool(ativo)
        self.ultimo_acesso = ultimo_acesso
        # Atributo privado (name mangling): equivale ao "-senhaHash" do diagrama
        self.__senha_hash: str | None = None
        if senha is not None:
            self.definir_senha(senha)
        elif senha_hash:
            self.__senha_hash = senha_hash  # usado ao carregar do arquivo JSON
        else:
            raise ErroValidacao("Informe a senha do usuário.")

    # ----------------------------------------------------------- propriedades
    @property
    def nome(self) -> str:
        return self._nome

    @nome.setter
    def nome(self, valor: str) -> None:
        valor = (valor or "").strip()
        if not valor:
            raise ErroValidacao("O nome do usuário é obrigatório.")
        self._nome = valor

    @property
    def login(self) -> str:
        return self._login

    @login.setter
    def login(self, valor: str) -> None:
        valor = (valor or "").strip().lower()
        if not valor or " " in valor:
            raise ErroValidacao("O login é obrigatório e não pode ter espaços.")
        self._login = valor

    @property
    def perfil(self) -> Perfil:
        return self._perfil

    @perfil.setter
    def perfil(self, valor: Perfil) -> None:
        if not isinstance(valor, Perfil):
            raise ErroValidacao("Todo usuário precisa de um perfil válido.")
        self._perfil = valor

    @property
    def ativo(self) -> bool:
        return self._ativo

    @property
    def senha_hash(self) -> str:
        """Leitura do hash, usada apenas para gravar em arquivo (nunca a senha)."""
        return self.__senha_hash

    # --------------------------------------------------------------- senha
    @classmethod
    def _gerar_hash(cls, senha: str, sal: str) -> str:
        bruto = hashlib.pbkdf2_hmac("sha256", senha.encode(), sal.encode(), cls._ITERACOES_HASH)
        return bruto.hex()

    def definir_senha(self, nova_senha: str) -> None:
        """RNF05: mínimo de 8 caracteres, guardada só como hash."""
        if not isinstance(nova_senha, str) or len(nova_senha) < self.TAMANHO_MINIMO_SENHA:
            raise ErroValidacao(
                f"A senha deve ter pelo menos {self.TAMANHO_MINIMO_SENHA} caracteres."
            )
        sal = secrets.token_hex(16)
        self.__senha_hash = f"{sal}${self._gerar_hash(nova_senha, sal)}"

    def autenticar(self, senha: str) -> bool:
        """Confere a senha. Usuário inativo nunca autentica (CA de RF10)."""
        if not self.ativo or not self.__senha_hash:
            return False
        sal, esperado = self.__senha_hash.split("$", 1)
        ok = hmac.compare_digest(self._gerar_hash(senha or "", sal), esperado)
        if ok:
            self.ultimo_acesso = datetime.now()
        return ok

    # --------------------------------------------------------------- perfil
    def tem_permissao(self, codigo: str) -> bool:
        return self.ativo and self.perfil.possui(codigo)

    def ativar(self) -> None:
        self._ativo = True

    def inativar(self) -> None:
        self._ativo = False

    # ---------------------------------------------------- métodos especiais
    def __eq__(self, outro: object) -> bool:
        """Dois usuários são o mesmo se têm o mesmo login."""
        if not isinstance(outro, Usuario):
            return NotImplemented
        return self.login == outro.login

    def __hash__(self) -> int:
        return hash(self.login)

    def __str__(self) -> str:
        situacao = "ativo" if self.ativo else "inativo"
        return f"{self.nome} ({self.login}) – {self.perfil.nome}, {situacao}"

    def __repr__(self) -> str:
        # O hash da senha fica de fora da representação de propósito.
        return f"Usuario(login={self.login!r}, perfil={self.perfil.nome!r}, ativo={self.ativo})"
