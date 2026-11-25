"""Testes de persistência: gravar, recarregar, backup, carga inicial."""

from __future__ import annotations

import json
from datetime import date, timedelta

import pytest

from indicadores_ve.excecoes import ErroSistema
from indicadores_ve.models import CicloPNCD, LevantamentoLIRAa, OrigemDado, StatusRelatorio
from indicadores_ve.persistence import Repositorio, RepositorioJSON, RepositorioMemoria
from indicadores_ve.services import Periodo, Sistema
from indicadores_ve.services.carga_inicial import carregar_dados_iniciais

from conftest import DADOS_INICIAIS, HOJE, SENHA


@pytest.fixture
def banco(tmp_path):
    return tmp_path / "banco.json"


@pytest.fixture
def sistema_json(banco, relogio):
    """Sistema com RepositorioJSON criado a partir dos dados iniciais."""
    repositorio = RepositorioJSON(banco, hoje=lambda: HOJE)
    carregar_dados_iniciais(repositorio, DADOS_INICIAIS, hoje=HOJE)
    return Sistema(repositorio, relogio=relogio)


def recarregar(banco, relogio) -> Sistema:
    """Simula fechar e abrir o programa de novo."""
    repositorio = RepositorioJSON(banco, hoje=lambda: HOJE)
    repositorio.carregar()
    return Sistema(repositorio, relogio=relogio)


class TestContrato:
    def test_repositorio_e_abstrato(self):
        with pytest.raises(TypeError):
            Repositorio()

    def test_implementacoes_herdam_do_contrato(self, banco):
        assert isinstance(RepositorioMemoria(), Repositorio)
        assert isinstance(RepositorioJSON(banco), Repositorio)
        assert repr(RepositorioJSON(banco)).startswith("RepositorioJSON(")

    def test_carregar_sem_arquivo_gera_banco_vazio(self, banco):
        repositorio = RepositorioJSON(banco)
        repositorio.carregar()
        assert repositorio.listar_usuarios() == [] and not banco.exists()


class TestIdaEVolta:
    def test_dados_sobrevivem_ao_fechar_o_programa(self, sistema_json, banco, relogio):
        dig = sistema_json.autenticacao.entrar("digitador", "digit2026").usuario
        sistema_json.lancamentos.lancar_valor(dig, "DENGUE", 2026, 9, 98)
        recarregado = recarregar(banco, relogio)
        assert recarregado.indicadores.total_indicador("DENGUE", Periodo.mes(2026, 9)) == 98
        assert len(recarregado.repositorio.listar_registros()) == len(sistema_json.repositorio.listar_registros())

    def test_herança_subclasses_sao_recriadas(self, sistema_json, banco, relogio):
        repo = recarregar(banco, relogio).repositorio
        ciclo = repo.obter_registro(("PNCD", 2026, 3))
        liraa = repo.obter_registro(("LIRAA", "2026-06-29"))
        assert isinstance(ciclo, CicloPNCD) and ciclo.cobertura() == 98.57
        assert isinstance(liraa, LevantamentoLIRAa) and liraa.classificar_risco() == "satisfatório"

    def test_associacoes_reconstruidas_como_objetos(self, sistema_json, banco, relogio):
        repo = recarregar(banco, relogio).repositorio
        lancamento = repo.obter_registro(("LANCAMENTO", "DENGUE", 2026, 5))
        assert lancamento.indicador is repo.buscar_indicador("DENGUE")
        assert lancamento.registrado_por is repo.obter_usuario("digitador")

    def test_agregacao_permissoes_compartilhadas_apos_recarga(self, sistema_json, banco, relogio):
        repo = recarregar(banco, relogio).repositorio
        gestor, coordenador = repo.obter_perfil("Gestor"), repo.obter_perfil("Coordenador")
        comuns = gestor.permissoes & coordenador.permissoes
        assert comuns
        for permissao in comuns:
            assert any(p is permissao for p in coordenador.permissoes)

    def test_composicao_indicadores_gravados_dentro_do_modulo(self, sistema_json, banco):
        dados = json.loads(banco.read_text(encoding="utf-8"))
        sinan = next(m for m in dados["modulos"] if m["sigla"] == "SINAN")
        assert len(sinan["indicadores"]) == 29

    def test_rnf05_senha_nunca_gravada(self, sistema_json, banco, relogio):
        texto = banco.read_text(encoding="utf-8")
        for senha in ("digit2026", "coord2026", "gestor2026", "admin2026"):
            assert senha not in texto
        recarregado = recarregar(banco, relogio)
        assert recarregado.repositorio.obter_usuario("coordenador").autenticar("coord2026")

    def test_homologacao_usuario_inativo_importacao_e_logs_persistem(self, sistema_json, banco, relogio):
        s = sistema_json
        coord = s.repositorio.obter_usuario("coordenador")
        admin = s.repositorio.obter_usuario("admin")
        dig = s.repositorio.obter_usuario("digitador")
        imp = s.importacao.pre_visualizar(dig, "modulo;codigo_indicador;ano;mes;valor\nSINAN;DENGUE;2026;9;98\n", "set.csv")
        s.importacao.confirmar(dig, imp.id)
        s.relatorios.homologar(coord, 2026, 2)
        s.usuarios.inativar(admin, "gestor")
        quantidade_logs = len(s.auditoria.listar())

        r = recarregar(banco, relogio)
        relatorio = r.repositorio.obter_relatorio(2026, 2)
        assert relatorio.status is StatusRelatorio.HOMOLOGADO and relatorio.homologado_por == "coordenador"
        assert not r.repositorio.obter_usuario("gestor").ativo
        assert r.repositorio.obter_importacao(imp.id).linhas_validas == 1
        assert r.repositorio.obter_registro(("LANCAMENTO", "DENGUE", 2026, 9)).origem is OrigemDado.IMPORTACAO
        assert len(r.auditoria.listar()) == quantidade_logs

    def test_ids_continuam_depois_de_recarregar(self, sistema_json, banco, relogio):
        maior = max(r.id for r in sistema_json.repositorio.listar_registros())
        r = recarregar(banco, relogio)
        dig = r.repositorio.obter_usuario("digitador")
        assert r.lancamentos.lancar_valor(dig, "DENGUE", 2026, 9, 1).id == maior + 1

    def test_reabertura_e_justificativa_persistem(self, sistema_json, banco, relogio):
        coord = sistema_json.repositorio.obter_usuario("coordenador")
        sistema_json.relatorios.homologar(coord, 2026, 2)
        sistema_json.relatorios.reabrir(coord, 2026, 2, "Correção do total de dengue")
        relatorio = recarregar(banco, relogio).repositorio.obter_relatorio(2026, 2)
        assert relatorio.versao == 2 and relatorio.justificativas == ("Correção do total de dengue",)


class TestRobustez:
    def test_arquivo_corrompido_mostra_mensagem_clara(self, banco):
        banco.write_text("{ isto não é json", encoding="utf-8")
        with pytest.raises(ErroSistema, match="corrompido"):
            RepositorioJSON(banco).carregar()

    def test_gravacao_nao_deixa_arquivo_temporario(self, sistema_json, banco):
        sistema_json.repositorio.salvar()
        assert not banco.with_suffix(".tmp").exists()


class TestBackup:
    def test_a10_backup_diario_com_retencao_de_30_dias(self, sistema_json, banco):
        dia = [HOJE]
        repositorio = RepositorioJSON(banco, hoje=lambda: dia[0])
        repositorio.carregar()
        for d in range(0, 40, 5):
            dia[0] = HOJE + timedelta(days=d)
            repositorio.salvar()
        backups = sorted(p.name for p in (banco.parent / "backups").glob("banco_*.json"))
        assert backups[0] == f"banco_{(HOJE + timedelta(days=5)).isoformat()}.json"  # o mais antigo saiu
        assert backups[-1] == f"banco_{(HOJE + timedelta(days=35)).isoformat()}.json"

    def test_backup_guarda_o_estado_anterior(self, sistema_json, banco):
        antes = banco.read_text(encoding="utf-8")
        dig = sistema_json.repositorio.obter_usuario("digitador")
        sistema_json.lancamentos.lancar_valor(dig, "DENGUE", 2026, 9, 1)
        backup = banco.parent / "backups" / f"banco_{HOJE.isoformat()}.json"
        assert backup.read_text(encoding="utf-8") == antes

    def test_sem_banco_nao_ha_backup(self, banco):
        assert RepositorioJSON(banco).fazer_backup() is None


class TestCargaInicial:
    def test_carga_com_dados_reais(self, tmp_path):
        resumo = carregar_dados_iniciais(RepositorioMemoria(), DADOS_INICIAIS, hoje=HOJE)
        assert (resumo["usuarios"], resumo["indicadores"], resumo["registros"]) == (4, 81, 311)

    def test_rn06_carga_evidencia_erros_de_soma_do_relatorio(self):
        conferencia = carregar_dados_iniciais(RepositorioMemoria(), DADOS_INICIAIS, hoje=HOJE)["conferencia"]
        assert conferencia["SINAN_2026_Q2"] == {"calculado": 2054, "informado": 2372}
        assert conferencia["LACEN_2026_Q2"] == {"calculado": 2815, "informado": 2818}
        assert conferencia["LAB_PACIENTES_2026_Q2"] == {"calculado": 1790, "informado": 1490}

    def test_carga_recria_do_zero(self):
        repositorio = RepositorioMemoria()
        carregar_dados_iniciais(repositorio, DADOS_INICIAIS, hoje=HOJE)
        carregar_dados_iniciais(repositorio, DADOS_INICIAIS, hoje=HOJE)
        assert len(repositorio.listar_usuarios()) == 4

    def test_usuarios_de_demonstracao_entram(self, sistema_real):
        for login, senha in [("admin", "admin2026"), ("coordenador", "coord2026"),
                             ("gestor", "gestor2026"), ("digitador", "digit2026")]:
            assert sistema_real.autenticacao.entrar(login, senha).usuario.login == login
