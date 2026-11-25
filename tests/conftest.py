"""Fixtures compartilhadas pelos testes.

- O relógio é FIXO (24/11/2026 10:00) para os testes não dependerem do dia
  em que forem executados. Ele pode ser avançado (ex.: sessão expirada).
- Os testes usam RepositorioMemoria: nada é gravado em disco, exceto nos
  testes de persistência, que usam a pasta temporária do pytest (tmp_path).
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

from indicadores_ve.models import Modulo, Periodicidade, TipoValor, Usuario
from indicadores_ve.persistence import RepositorioMemoria
from indicadores_ve.services import (
    ADMINISTRADOR,
    COORDENADOR,
    DIGITADOR,
    GESTOR,
    Sistema,
    criar_perfis_padrao,
)
from indicadores_ve.services.carga_inicial import carregar_dados_iniciais

RAIZ = Path(__file__).resolve().parent.parent
DADOS_INICIAIS = RAIZ / "data" / "dados_iniciais.json"
HOJE = date(2026, 11, 24)
SENHA = "senha1234"


class RelogioFalso:
    """Relógio controlado pelos testes."""

    def __init__(self, inicio: datetime) -> None:
        self.agora = inicio

    def __call__(self) -> datetime:
        return self.agora

    def avancar(self, **tempo) -> None:
        self.agora += timedelta(**tempo)


@pytest.fixture
def relogio() -> RelogioFalso:
    return RelogioFalso(datetime(2026, 11, 24, 10, 0))


@pytest.fixture
def repo() -> RepositorioMemoria:
    """Repositório com perfis, 4 usuários e módulos/indicadores de exemplo."""
    repositorio = RepositorioMemoria()
    for perfil in criar_perfis_padrao().values():
        repositorio.adicionar_perfil(perfil)
    for nome, login, perfil in [
        ("Técnico", "digitador", DIGITADOR),
        ("Gestor", "gestor", GESTOR),
        ("Coordenador", "coordenador", COORDENADOR),
        ("Administrador", "admin", ADMINISTRADOR),
    ]:
        repositorio.adicionar_usuario(Usuario(nome, login, repositorio.obter_perfil(perfil), senha=SENHA))

    sinan = repositorio.adicionar_modulo(Modulo("SINAN", "Agravos de Notificação"))
    sinan.adicionar_indicador("DENGUE", "Dengue", "Arboviroses")
    sinan.adicionar_indicador("CHIKUNGUNYA", "Chikungunya", "Arboviroses")
    sinan.adicionar_indicador("ZIKA", "Zika", "Arboviroses")
    sinan.adicionar_indicador("SIFILIS_ADULTO", "Sífilis em adulto", "IST/HIV/Aids")
    lacen = repositorio.adicionar_modulo(Modulo("LACEN", "Laboratório"))
    lacen.adicionar_indicador("LAC_TB_TRM", "Tuberculose – TRM", "Exames LACEN")
    vitais = repositorio.adicionar_modulo(Modulo("SIM_SINASC", "Dados vitais"))
    vitais.adicionar_indicador("NASCIDOS_VIVOS", "Nascidos vivos", "Nascimentos",
                               TipoValor.INTEIRO, Periodicidade.MENSAL)
    vitais.adicionar_indicador("OBITOS_TOTAL", "Total de óbitos", "Mortalidade")
    repositorio.adicionar_modulo(Modulo("ENDEMIAS", "Controle de Endemias"))
    return repositorio


@pytest.fixture
def sistema(repo, relogio) -> Sistema:
    return Sistema(repo, relogio=relogio)


@pytest.fixture
def digitador(repo):
    return repo.obter_usuario("digitador")


@pytest.fixture
def gestor(repo):
    return repo.obter_usuario("gestor")


@pytest.fixture
def coordenador(repo):
    return repo.obter_usuario("coordenador")


@pytest.fixture
def admin(repo):
    return repo.obter_usuario("admin")


@pytest.fixture
def endemias(repo):
    return repo.obter_modulo("ENDEMIAS")


@pytest.fixture
def dengue(repo):
    return repo.buscar_indicador("DENGUE")


@pytest.fixture
def sistema_real(relogio) -> Sistema:
    """Sistema carregado com os dados reais do relatório do 2º quadrimestre/2026."""
    repositorio = RepositorioMemoria()
    carregar_dados_iniciais(repositorio, DADOS_INICIAIS, hoje=HOJE)
    return Sistema(repositorio, relogio=relogio)
