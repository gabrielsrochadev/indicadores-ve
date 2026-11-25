"""Testes dos serviços (regras de negócio e casos de uso)."""

from __future__ import annotations

import csv
from datetime import date

import pytest

from indicadores_ve.excecoes import (
    AcessoNegado,
    DadoPessoalDetectado,
    ErroAutenticacao,
    ErroValidacao,
    PeriodoHomologado,
    RegistroDuplicado,
    RegistroNaoEncontrado,
)
from indicadores_ve.models import CicloPNCD, LancamentoMensal, LevantamentoLIRAa, OrigemDado
from indicadores_ve.services import Periodo, exigir_permissao
from indicadores_ve.services.exportadores import (
    ConteudoRelatorio,
    Exportador,
    ExportadorCSV,
    ExportadorTXT,
    TabelaRelatorio,
)
from indicadores_ve.services.indicadores import ServicoIndicadores

from conftest import SENHA

CABECALHO = "modulo;codigo_indicador;ano;mes;valor\n"


# =====================================================================
# Autenticação, sessão e permissões – RF09, RN03, RNF05
# =====================================================================
class TestAutenticacao:
    def test_login_valido_abre_sessao_e_registra_log(self, sistema):
        sessao = sistema.autenticacao.entrar("digitador", SENHA)
        assert sessao.usuario.login == "digitador"
        assert sistema.auditoria.listar(acao="login")[0].usuario == "digitador"

    def test_login_nao_diferencia_maiusculas(self, sistema):
        assert sistema.autenticacao.entrar("DIGITADOR", SENHA).usuario.login == "digitador"

    @pytest.mark.parametrize("login, senha", [("digitador", "errada123"), ("naoexiste", SENHA)])
    def test_login_invalido_com_mensagem_generica(self, sistema, login, senha):
        with pytest.raises(ErroAutenticacao, match="Login ou senha inválidos"):
            sistema.autenticacao.entrar(login, senha)

    def test_rnf05_sessao_expira_apos_30_minutos(self, sistema, relogio):
        sessao = sistema.autenticacao.entrar("gestor", SENHA)
        relogio.avancar(minutes=29)
        assert sistema.autenticacao.validar_sessao(sessao).login == "gestor"  # renova
        relogio.avancar(minutes=29)
        assert sistema.autenticacao.validar_sessao(sessao)  # ainda vale: foi renovada
        relogio.avancar(minutes=31)
        with pytest.raises(ErroAutenticacao, match="expirada"):
            sistema.autenticacao.validar_sessao(sessao)

    def test_sessao_encerrada_apos_sair(self, sistema):
        sessao = sistema.autenticacao.entrar("gestor", SENHA)
        sistema.autenticacao.sair(sessao)
        with pytest.raises(ErroAutenticacao):
            sistema.autenticacao.validar_sessao(sessao)

    def test_sessao_cai_se_usuario_for_inativado(self, sistema, admin):
        sessao = sistema.autenticacao.entrar("gestor", SENHA)
        sistema.usuarios.inativar(admin, "gestor")
        with pytest.raises(ErroAutenticacao, match="inativo"):
            sistema.autenticacao.validar_sessao(sessao)

    def test_sessao_str_repr(self, sistema):
        sessao = sistema.autenticacao.entrar("gestor", SENHA)
        assert str(sessao) == "Sessão de gestor desde 24/11/2026 10:00"
        assert repr(sessao) == "Sessao(usuario='gestor', encerrada=False)"

    def test_rn03_exigir_permissao(self, gestor):
        exigir_permissao(gestor, "ver_painel")
        with pytest.raises(AcessoNegado, match="Gestor"):
            exigir_permissao(gestor, "lancar_dados")


# =====================================================================
# Usuários – RF10
# =====================================================================
class TestUsuarios:
    def test_cadastrar(self, sistema, admin):
        novo = sistema.usuarios.cadastrar(admin, "Maria", "maria", "senhasegura", "Digitador")
        assert sistema.autenticacao.entrar("maria", "senhasegura").usuario == novo
        assert sistema.auditoria.listar(acao="incluir")[-1].entidade == "Usuario maria"

    def test_login_duplicado(self, sistema, admin):
        with pytest.raises(RegistroDuplicado):
            sistema.usuarios.cadastrar(admin, "Outro", "gestor", "senhasegura", "Gestor")

    def test_perfil_inexistente(self, sistema, admin):
        with pytest.raises(RegistroNaoEncontrado):
            sistema.usuarios.cadastrar(admin, "X", "x", "senhasegura", "Diretor")

    def test_somente_admin_gerencia(self, sistema, coordenador):
        with pytest.raises(AcessoNegado):
            sistema.usuarios.cadastrar(coordenador, "X", "x", "senhasegura", "Gestor")
        with pytest.raises(AcessoNegado):
            sistema.usuarios.listar(coordenador)

    def test_alterar_perfil(self, sistema, admin):
        usuario = sistema.usuarios.alterar_perfil(admin, "gestor", "Coordenador")
        assert usuario.tem_permissao("homologar_relatorio")

    def test_inativar_e_reativar(self, sistema, admin):
        sistema.usuarios.inativar(admin, "gestor")
        with pytest.raises(ErroAutenticacao):
            sistema.autenticacao.entrar("gestor", SENHA)
        sistema.usuarios.ativar(admin, "gestor")
        assert sistema.autenticacao.entrar("gestor", SENHA)

    def test_admin_nao_inativa_a_si_mesmo(self, sistema, admin):
        with pytest.raises(ErroValidacao):
            sistema.usuarios.inativar(admin, "admin")

    def test_redefinir_senha_sem_gravar_senha_no_log(self, sistema, admin):
        sistema.usuarios.redefinir_senha(admin, "gestor", "novasenha99")
        assert sistema.autenticacao.entrar("gestor", "novasenha99")
        assert all("novasenha99" not in str(log) for log in sistema.auditoria.listar())

    def test_listar_ordenado(self, sistema, admin):
        assert [u.login for u in sistema.usuarios.listar(admin)] == ["admin", "coordenador", "digitador", "gestor"]


# =====================================================================
# Lançamentos – RF01–RF04, RN04, RN05, RN11, RNF10
# =====================================================================
class TestLancamentos:
    def test_incluir_gera_auditoria(self, sistema, digitador):
        sistema.lancamentos.lancar_valor(digitador, "DENGUE", 2026, 5, 418)
        log = sistema.auditoria.listar(usuario="digitador")[-1]
        assert (log.acao, log.entidade, log.valor_novo) == ("incluir", "LancamentoMensal", "Dengue – 05/2026: 418")

    def test_registra_autor(self, sistema, digitador):
        lancamento = sistema.lancamentos.lancar_valor(digitador, "DENGUE", 2026, 5, 418)
        assert lancamento.registrado_por is digitador

    def test_rn04_duplicado_exige_confirmacao(self, sistema, digitador):
        sistema.lancamentos.lancar_valor(digitador, "DENGUE", 2026, 5, 418)
        with pytest.raises(RegistroDuplicado, match="Confirme a substituição"):
            sistema.lancamentos.lancar_valor(digitador, "DENGUE", 2026, 5, 420)
        substituto = sistema.lancamentos.lancar_valor(digitador, "DENGUE", 2026, 5, 420, confirmar_substituicao=True)
        assert sistema.indicadores.total_indicador("DENGUE", Periodo.mes(2026, 5)) == 420
        log = sistema.auditoria.listar(acao="substituir")[-1]
        assert (log.valor_anterior, log.valor_novo) == ("Dengue – 05/2026: 418", "Dengue – 05/2026: 420")
        assert substituto.id == sistema.repositorio.obter_registro(substituto.chave()).id

    def test_polimorfismo_registrar_aceita_os_tres_tipos(self, sistema, digitador, endemias, dengue):
        for registro in (
            LancamentoMensal(dengue, 2026, 5, 418),
            CicloPNCD(endemias, 2026, 3, 5, 40680, 40100),
            LevantamentoLIRAa(endemias, date(2026, 6, 29), date(2026, 7, 4), 0.2, 0.2),
        ):
            sistema.lancamentos.registrar(digitador, registro)
        tipos = {type(r).__name__ for r in sistema.repositorio.listar_registros()}
        assert tipos == {"LancamentoMensal", "CicloPNCD", "LevantamentoLIRAa"}

    def test_rn05_mes_nao_encerrado(self, sistema, digitador):
        with pytest.raises(ErroValidacao):
            sistema.lancamentos.lancar_valor(digitador, "DENGUE", 2026, 11, 1)

    def test_indicador_inexistente(self, sistema, digitador):
        with pytest.raises(RegistroNaoEncontrado):
            sistema.lancamentos.lancar_valor(digitador, "FEBRE_AMARELA", 2026, 5, 1)

    @pytest.mark.parametrize("perfil", ["gestor", "coordenador", "admin"])
    def test_rn03_so_digitador_lanca(self, sistema, repo, perfil):
        with pytest.raises(AcessoNegado):
            sistema.lancamentos.lancar_valor(repo.obter_usuario(perfil), "DENGUE", 2026, 5, 1)

    def test_rn11_excluir_e_bloqueado_em_periodo_homologado(self, sistema, digitador, coordenador):
        lancamento = sistema.lancamentos.lancar_valor(digitador, "DENGUE", 2026, 5, 418)
        sistema.relatorios.homologar(coordenador, 2026, 2)
        with pytest.raises(PeriodoHomologado):
            sistema.lancamentos.excluir(digitador, lancamento)

    def test_excluir(self, sistema, digitador):
        lancamento = sistema.lancamentos.lancar_valor(digitador, "DENGUE", 2026, 5, 418)
        sistema.lancamentos.excluir(digitador, lancamento)
        assert not sistema.lancamentos.existe(lancamento)
        assert sistema.auditoria.listar(acao="excluir")[-1].valor_anterior == "Dengue – 05/2026: 418"

    def test_rn11_bloqueio_vale_so_para_o_quadrimestre_homologado(self, sistema, digitador, coordenador):
        sistema.lancamentos.lancar_valor(digitador, "DENGUE", 2026, 5, 418)
        sistema.relatorios.homologar(coordenador, 2026, 2)
        sistema.lancamentos.lancar_valor(digitador, "DENGUE", 2026, 9, 10)  # 3º quadrimestre: liberado
        with pytest.raises(PeriodoHomologado):
            sistema.lancamentos.lancar_valor(digitador, "DENGUE", 2026, 8, 10)


# =====================================================================
# Importação – RF11, RF12, RN01
# =====================================================================
class TestImportacao:
    def test_previa_nao_grava_nada(self, sistema, digitador):
        imp = sistema.importacao.pre_visualizar(digitador, CABECALHO + "SINAN;DENGUE;2026;5;418\n")
        assert imp.linhas_validas == 1
        assert sistema.repositorio.lancamentos() == []

    def test_confirmar_grava_com_origem_importacao(self, sistema, digitador):
        imp = sistema.importacao.pre_visualizar(digitador, CABECALHO + "SINAN;DENGUE;2026;5;418\n")
        assert sistema.importacao.confirmar(digitador, imp.id) == {"inseridos": 1, "substituidos": 0, "rejeitados": 0}
        lancamento = sistema.repositorio.lancamentos()[0]
        assert lancamento.origem is OrigemDado.IMPORTACAO and lancamento.importacao_id == imp.id

    def test_linhas_com_erro_indicam_numero_e_motivo(self, sistema, digitador):
        conteudo = CABECALHO + (
            "SINAN;DENGUE;2026;5;418\n"      # linha 2 ok
            "SINAN;DENGUE;2026;6;-3\n"       # linha 3 negativo
            "SINAN;XPTO;2026;6;1\n"          # linha 4 indicador inexistente
            "SINAN;ZIKA;2026;12;1\n"         # linha 5 mês aberto
            "SINAN;ZIKA;dois mil;6;1\n"      # linha 6 ano inválido
            "SINAN;ZIKA;2026;6;abc\n"        # linha 7 valor inválido
            "SINAN;DENGUE;2026;5;1\n"        # linha 8 repetida no arquivo
        )
        imp = sistema.importacao.pre_visualizar(digitador, conteudo, "lote.csv")
        erros = dict(imp.erros)
        assert imp.linhas_validas == 1 and len(imp) == 7
        assert sorted(erros) == [3, 4, 5, 6, 7, 8]
        assert "negativo" in erros[3] and "não encontrado" in erros[4]
        assert "ainda não terminou" in erros[5] and "repetida" in erros[8]

    def test_aceita_virgula_como_separador_e_cabecalho_com_acento(self, sistema, digitador):
        conteudo = "Módulo,Código Indicador,Ano,Mês,Valor\nSINAN,DENGUE,2026,5,418\n"
        imp = sistema.importacao.pre_visualizar(digitador, conteudo)
        assert imp.linhas_validas == 1

    @pytest.mark.parametrize("coluna", ["nome_paciente", "CPF", "Cartão SUS", "endereco", "data_nascimento", "nome"])
    def test_rn01_colunas_de_dado_pessoal_rejeitam_o_arquivo(self, sistema, digitador, coluna):
        conteudo = f"modulo;codigo_indicador;ano;mes;valor;{coluna}\nSINAN;DENGUE;2026;5;1;x\n"
        with pytest.raises(DadoPessoalDetectado, match="LGPD"):
            sistema.importacao.pre_visualizar(digitador, conteudo)

    def test_colunas_obrigatorias_ausentes(self, sistema, digitador):
        with pytest.raises(ErroValidacao, match="ausentes: valor"):
            sistema.importacao.pre_visualizar(digitador, "modulo;codigo_indicador;ano;mes\nSINAN;DENGUE;2026;5\n")

    def test_arquivo_vazio(self, sistema, digitador):
        with pytest.raises(ErroValidacao, match="vazio"):
            sistema.importacao.pre_visualizar(digitador, "  ")

    def test_conflito_marcado_na_previa_e_substituido_na_confirmacao(self, sistema, digitador):
        sistema.lancamentos.lancar_valor(digitador, "DENGUE", 2026, 5, 400)
        imp = sistema.importacao.pre_visualizar(digitador, CABECALHO + "SINAN;DENGUE;2026;5;418\n")
        assert imp.validas[0]["substitui"] is True
        assert sistema.importacao.confirmar(digitador, imp.id)["substituidos"] == 1
        assert sistema.indicadores.total_indicador("DENGUE", Periodo.mes(2026, 5)) == 418

    def test_confirmacao_e_tudo_ou_nada(self, sistema, digitador, coordenador):
        """Se o período for homologado entre a prévia e a confirmação, nada é gravado."""
        sistema.lancamentos.lancar_valor(digitador, "ZIKA", 2026, 5, 1)
        imp = sistema.importacao.pre_visualizar(
            digitador, CABECALHO + "SINAN;DENGUE;2026;9;10\nSINAN;DENGUE;2026;5;418\n"
        )
        sistema.relatorios.homologar(coordenador, 2026, 2)
        with pytest.raises(PeriodoHomologado):
            sistema.importacao.confirmar(digitador, imp.id)
        assert not any(l.indicador.codigo == "DENGUE" for l in sistema.repositorio.lancamentos())

    def test_cancelar(self, sistema, digitador):
        imp = sistema.importacao.pre_visualizar(digitador, CABECALHO + "SINAN;DENGUE;2026;5;418\n")
        sistema.importacao.cancelar(digitador, imp.id)
        with pytest.raises(ErroValidacao):
            sistema.importacao.confirmar(digitador, imp.id)

    def test_gestor_nao_importa(self, sistema, gestor):
        with pytest.raises(AcessoNegado):
            sistema.importacao.pre_visualizar(gestor, CABECALHO)

    def test_pre_visualizar_arquivo(self, sistema, digitador, tmp_path):
        arquivo = tmp_path / "setembro.csv"
        arquivo.write_text(CABECALHO + "SINAN;DENGUE;2026;9;98\n", encoding="utf-8-sig")
        imp = sistema.importacao.pre_visualizar_arquivo(digitador, arquivo)
        assert imp.nome_arquivo == "setembro.csv" and imp.linhas_validas == 1


# =====================================================================
# Indicadores – RF05–RF07, RF13, RN06, RN07, RN10
# =====================================================================
class TestIndicadores:
    @pytest.mark.parametrize(
        "atual, anterior, esperado, texto",
        [(1191, 1000, 19.1, "+19,1%"), (557, 598, -6.9, "-6,9%"), (5, 0, None, "—"), (0, 0, None, "—")],
    )
    def test_rn07_variacao(self, atual, anterior, esperado, texto):
        variacao = ServicoIndicadores.variacao_percentual(atual, anterior)
        assert variacao == esperado
        assert ServicoIndicadores.formatar_variacao(variacao) == texto

    def test_periodo_rn10(self):
        assert Periodo.quadrimestre(2026, 2).meses == [5, 6, 7, 8]
        assert Periodo.anual(2026).meses == list(range(1, 13))
        assert Periodo.mes(2026, 5).mesmo_periodo_ano_anterior() == Periodo.mes(2025, 5)
        assert [str(Periodo.mes(2026, 5)), str(Periodo.quadrimestre(2026, 2)), str(Periodo.anual(2026))] == \
            ["05/2026", "2º quadrimestre/2026", "2026"]
        assert len({Periodo.mes(2026, 5), Periodo.mes(2026, 5)}) == 1  # frozen: __eq__ e __hash__

    @pytest.mark.parametrize("tipo, numero", [("semana", 1), ("mes", 13), ("quadrimestre", 4)])
    def test_periodo_invalido(self, tipo, numero):
        with pytest.raises(ErroValidacao):
            Periodo(tipo, 2026, numero)

    def test_comparar_periodos_de_tipos_diferentes_rn10(self, sistema, gestor):
        with pytest.raises(ErroValidacao, match="mesmo tipo"):
            sistema.indicadores.comparar(gestor, Periodo.quadrimestre(2026, 2), Periodo.anual(2025))

    def test_comparar_ignora_indicadores_sem_dados(self, sistema, digitador, gestor):
        sistema.lancamentos.lancar_valor(digitador, "DENGUE", 2026, 5, 10)
        linhas = sistema.indicadores.comparar(gestor, Periodo.mes(2026, 5), Periodo.mes(2025, 5))
        assert [l.codigo for l in linhas] == ["DENGUE"] and linhas[0].variacao is None

    def test_admin_nao_ve_painel(self, sistema, admin):
        with pytest.raises(AcessoNegado):
            sistema.indicadores.painel(admin)

    def test_painel_sem_dados(self, sistema, gestor):
        with pytest.raises(ErroValidacao, match="Ainda não há lançamentos"):
            sistema.indicadores.painel(gestor)

    def test_painel_oculta_cartoes_sem_dados(self, sistema, digitador, gestor):
        sistema.lancamentos.lancar_valor(digitador, "DENGUE", 2026, 5, 10)
        titulos = [c.titulo for c in sistema.indicadores.painel(gestor).cartoes]
        assert titulos == ["Notificações (SINAN)"]

    def test_ranking_e_serie(self, sistema, digitador):
        for codigo, valor in [("DENGUE", 50), ("ZIKA", 0), ("CHIKUNGUNYA", 5)]:
            sistema.lancamentos.lancar_valor(digitador, codigo, 2026, 5, valor)
        q2 = Periodo.quadrimestre(2026, 2)
        sinan = sistema.indicadores.filtrar_indicadores(modulo="SINAN")
        assert sistema.indicadores.ranking(sinan, q2) == [("Dengue", 50), ("Chikungunya", 5)]
        assert sistema.indicadores.serie_mensal(sinan, q2) == {"mai": 55, "jun": 0, "jul": 0, "ago": 0}

    def test_grupos(self, sistema):
        assert sistema.indicadores.grupos("SINAN") == ["Arboviroses", "IST/HIV/Aids"]


# =====================================================================
# Relatórios – RF08, RF14
# =====================================================================
class TestRelatorios:
    def test_nao_homologa_periodo_sem_dados(self, sistema, coordenador):
        with pytest.raises(ErroValidacao, match="Não há lançamentos"):
            sistema.relatorios.homologar(coordenador, 2026, 2)

    def test_gestor_nao_homologa(self, sistema, digitador, gestor):
        sistema.lancamentos.lancar_valor(digitador, "DENGUE", 2026, 5, 1)
        with pytest.raises(AcessoNegado):
            sistema.relatorios.homologar(gestor, 2026, 2)

    def test_reabrir_libera_e_gera_nova_versao(self, sistema, digitador, coordenador):
        sistema.lancamentos.lancar_valor(digitador, "DENGUE", 2026, 5, 1)
        sistema.relatorios.homologar(coordenador, 2026, 2)
        relatorio = sistema.relatorios.reabrir(coordenador, 2026, 2, "Correção de digitação em maio")
        assert relatorio.versao == 2
        sistema.lancamentos.lancar_valor(digitador, "DENGUE", 2026, 5, 2, confirmar_substituicao=True)
        assert [l.acao for l in sistema.auditoria.listar(usuario="coordenador")] == ["homologar", "reabrir"]

    def test_digitador_nao_exporta(self, sistema, digitador, tmp_path):
        with pytest.raises(AcessoNegado):
            sistema.relatorios.exportar(digitador, 2026, 2, "csv", tmp_path)

    def test_formato_nao_suportado(self, sistema, gestor, tmp_path):
        with pytest.raises(ErroValidacao, match="não suportado"):
            sistema.relatorios.exportar(gestor, 2026, 2, "pdf", tmp_path)

    def test_exportar_txt_e_csv_mesmo_conteudo(self, sistema, digitador, gestor, endemias, tmp_path):
        sistema.lancamentos.lancar_valor(digitador, "DENGUE", 2026, 5, 418)
        sistema.lancamentos.registrar(digitador, CicloPNCD(endemias, 2026, 3, 5, 40680, 40100))
        sistema.lancamentos.registrar(digitador, LevantamentoLIRAa(endemias, date(2026, 6, 29), date(2026, 7, 4), 0.2, 0.2))
        txt = sistema.relatorios.exportar(gestor, 2026, 2, "txt", tmp_path).read_text(encoding="utf-8")
        planilha = sistema.relatorios.exportar(gestor, 2026, 2, "csv", tmp_path)
        celulas = [c for linha in csv.reader(planilha.open(encoding="utf-8-sig"), delimiter=";") for c in linha]
        for esperado in ("Dengue", "418", "98,57", "satisfatório", "RASCUNHO"):
            assert esperado in txt and esperado in " ".join(celulas)
        assert sistema.auditoria.listar(acao="exportar")[-1].valor_novo == "relatorio_2026_Q2_v1.csv"


class TestExportadores:
    """Polimorfismo: o mesmo conteúdo gerado em dois formatos."""

    CONTEUDO = ConteudoRelatorio(
        cabecalho=["SMS Balsas"],
        tabelas=[TabelaRelatorio("SINAN", ["Indicador", "Total"], [["Dengue", 1191], ["Cobertura", 98.57]])],
    )

    def test_exportador_e_abstrato(self):
        with pytest.raises(TypeError):
            Exportador()

    @pytest.mark.parametrize("exportador", [ExportadorCSV(), ExportadorTXT()])
    def test_cada_formato_gera_o_mesmo_conteudo(self, exportador):
        texto = exportador.gerar(self.CONTEUDO)
        assert "SMS Balsas" in texto and "Dengue" in texto and "1191" in texto and "98,57" in texto

    def test_csv_usa_ponto_e_virgula(self):
        assert "Dengue;1191" in ExportadorCSV().gerar(self.CONTEUDO)
        assert str(ExportadorCSV()) == "CSV" and str(ExportadorTXT()) == "TXT"
