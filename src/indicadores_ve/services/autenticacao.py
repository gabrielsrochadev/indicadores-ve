"""Autenticação, sessão e controle de acesso (RF09, RN03, RNF05 – UC01)."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Callable

from ..excecoes import AcessoNegado, ErroAutenticacao, RegistroNaoEncontrado
from ..models import Usuario
from ..persistence import Repositorio
from .auditoria import ServicoAuditoria


def exigir_permissao(usuario: Usuario, codigo: str) -> None:
    """RN03: lança AcessoNegado se o perfil do usuário não tiver a permissão."""
    if not usuario.tem_permissao(codigo):
        raise AcessoNegado(
            f"Acesso negado: o perfil {usuario.perfil.nome} não pode executar esta ação."
        )


class Sessao:
    """Sessão de um usuário logado. Expira após um tempo sem uso (RNF05)."""

    def __init__(self, usuario: Usuario, inicio: datetime, tempo_limite: timedelta) -> None:
        self.usuario = usuario
        self.inicio = inicio
        self.ultimo_uso = inicio
        self.tempo_limite = tempo_limite
        self.encerrada = False

    def expirou(self, agora: datetime) -> bool:
        return self.encerrada or agora - self.ultimo_uso > self.tempo_limite

    def renovar(self, agora: datetime) -> None:
        self.ultimo_uso = agora

    def __str__(self) -> str:
        return f"Sessão de {self.usuario.login} desde {self.inicio:%d/%m/%Y %H:%M}"

    def __repr__(self) -> str:
        return f"Sessao(usuario={self.usuario.login!r}, encerrada={self.encerrada})"


class ServicoAutenticacao:
    TEMPO_LIMITE_PADRAO = timedelta(minutes=30)  # RNF05

    def __init__(
        self,
        repositorio: Repositorio,
        auditoria: ServicoAuditoria,
        relogio: Callable[[], datetime] = datetime.now,
        tempo_limite: timedelta = TEMPO_LIMITE_PADRAO,
    ) -> None:
        self._repo = repositorio
        self._auditoria = auditoria
        self._relogio = relogio
        self._tempo_limite = tempo_limite

    def entrar(self, login: str, senha: str) -> Sessao:
        """UC01: login individual. A mensagem de erro não diz qual dado está errado."""
        try:
            usuario = self._repo.obter_usuario(login)
        except RegistroNaoEncontrado:
            raise ErroAutenticacao("Login ou senha inválidos.") from None
        if not usuario.ativo:
            raise ErroAutenticacao("Usuário inativo. Procure o Administrador.")
        if not usuario.autenticar(senha):
            raise ErroAutenticacao("Login ou senha inválidos.")
        self._auditoria.registrar(usuario.login, "login", "Sessao")
        self._repo.salvar()
        return Sessao(usuario, self._relogio(), self._tempo_limite)

    def validar_sessao(self, sessao: Sessao) -> Usuario:
        """Confere se a sessão ainda vale; se valer, renova o prazo."""
        agora = self._relogio()
        if sessao.expirou(agora):
            sessao.encerrada = True
            raise ErroAutenticacao("Sessão expirada. Entre novamente.")
        if not sessao.usuario.ativo:
            sessao.encerrada = True
            raise ErroAutenticacao("Usuário inativo.")
        sessao.renovar(agora)
        return sessao.usuario

    def sair(self, sessao: Sessao) -> None:
        sessao.encerrada = True
        self._auditoria.registrar(sessao.usuario.login, "logout", "Sessao")
        self._repo.salvar()
