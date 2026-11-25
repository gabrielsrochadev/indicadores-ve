"""Gestão de usuários e perfis (RF10 – UC02) e perfis padrão (SRS seção 6)."""

from __future__ import annotations

from ..excecoes import ErroValidacao
from ..models import Perfil, Permissao, Usuario
from ..persistence import Repositorio
from .auditoria import ServicoAuditoria
from .autenticacao import exigir_permissao

# Nomes dos perfis da SRS
DIGITADOR = "Digitador"
COORDENADOR = "Coordenador"
GESTOR = "Gestor"
ADMINISTRADOR = "Administrador"


def criar_permissoes_padrao() -> dict[str, Permissao]:
    return {
        Permissao.LANCAR_DADOS: Permissao(Permissao.LANCAR_DADOS, "Lançar e corrigir dados"),
        Permissao.IMPORTAR_PLANILHA: Permissao(Permissao.IMPORTAR_PLANILHA, "Importar planilha"),
        Permissao.VER_PAINEL: Permissao(Permissao.VER_PAINEL, "Ver painel e comparativos"),
        Permissao.EXPORTAR_RELATORIO: Permissao(Permissao.EXPORTAR_RELATORIO, "Exportar relatórios"),
        Permissao.HOMOLOGAR_RELATORIO: Permissao(Permissao.HOMOLOGAR_RELATORIO, "Homologar relatório"),
        Permissao.GERENCIAR_USUARIOS: Permissao(Permissao.GERENCIAR_USUARIOS, "Gerenciar usuários"),
    }


def criar_perfis_padrao() -> dict[str, Perfil]:
    """Quadro 3 da SRS. As mesmas instâncias de Permissao são compartilhadas
    entre perfis (agregação). O Coordenador = permissões do Gestor + homologar,
    que é a generalização Coordenador → Gestor do diagrama de casos de uso."""
    p = criar_permissoes_padrao()
    gestor = [p[Permissao.VER_PAINEL], p[Permissao.EXPORTAR_RELATORIO]]
    return {
        DIGITADOR: Perfil(
            DIGITADOR,
            "Técnicos da VE",
            [p[Permissao.LANCAR_DADOS], p[Permissao.IMPORTAR_PLANILHA], p[Permissao.VER_PAINEL]],
        ),
        GESTOR: Perfil(GESTOR, "Secretário e gestores de saúde", gestor),
        COORDENADOR: Perfil(
            COORDENADOR, "Coordenador do setor", gestor + [p[Permissao.HOMOLOGAR_RELATORIO]]
        ),
        ADMINISTRADOR: Perfil(
            ADMINISTRADOR, "Servidor designado pela SMS", [p[Permissao.GERENCIAR_USUARIOS]]
        ),
    }


class ServicoUsuarios:
    def __init__(self, repositorio: Repositorio, auditoria: ServicoAuditoria) -> None:
        self._repo = repositorio
        self._auditoria = auditoria

    def cadastrar(self, admin: Usuario, nome: str, login: str, senha: str, perfil: str) -> Usuario:
        exigir_permissao(admin, Permissao.GERENCIAR_USUARIOS)
        usuario = Usuario(nome, login, self._repo.obter_perfil(perfil), senha=senha)
        self._repo.adicionar_usuario(usuario)  # RegistroDuplicado se o login existir
        self._auditoria.registrar(admin.login, "incluir", f"Usuario {usuario.login}", None, perfil)
        self._repo.salvar()
        return usuario

    def alterar_perfil(self, admin: Usuario, login: str, perfil: str) -> Usuario:
        exigir_permissao(admin, Permissao.GERENCIAR_USUARIOS)
        usuario = self._repo.obter_usuario(login)
        anterior = usuario.perfil.nome
        usuario.perfil = self._repo.obter_perfil(perfil)
        self._auditoria.registrar(admin.login, "alterar_perfil", f"Usuario {login}", anterior, perfil)
        self._repo.salvar()
        return usuario

    def inativar(self, admin: Usuario, login: str) -> Usuario:
        exigir_permissao(admin, Permissao.GERENCIAR_USUARIOS)
        usuario = self._repo.obter_usuario(login)
        if usuario == admin:
            raise ErroValidacao("O administrador não pode inativar a própria conta.")
        usuario.inativar()
        self._auditoria.registrar(admin.login, "inativar", f"Usuario {login}", "ativo", "inativo")
        self._repo.salvar()
        return usuario

    def ativar(self, admin: Usuario, login: str) -> Usuario:
        exigir_permissao(admin, Permissao.GERENCIAR_USUARIOS)
        usuario = self._repo.obter_usuario(login)
        usuario.ativar()
        self._auditoria.registrar(admin.login, "ativar", f"Usuario {login}", "inativo", "ativo")
        self._repo.salvar()
        return usuario

    def redefinir_senha(self, admin: Usuario, login: str, nova_senha: str) -> None:
        exigir_permissao(admin, Permissao.GERENCIAR_USUARIOS)
        usuario = self._repo.obter_usuario(login)
        usuario.definir_senha(nova_senha)
        # A senha nunca vai para o log, nem como valor anterior/novo.
        self._auditoria.registrar(admin.login, "redefinir_senha", f"Usuario {login}")
        self._repo.salvar()

    def listar(self, admin: Usuario) -> list[Usuario]:
        exigir_permissao(admin, Permissao.GERENCIAR_USUARIOS)
        return sorted(self._repo.listar_usuarios(), key=lambda u: u.login)
