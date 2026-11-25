"""Testes das classes de domínio: criação, encapsulamento, herança,
polimorfismo, abstração, relacionamentos e métodos especiais."""

from __future__ import annotations

from datetime import date, datetime

import pytest

from indicadores_ve.excecoes import AcessoNegado, ErroValidacao, RegistroDuplicado, RegistroNaoEncontrado
from indicadores_ve.models import (
    CicloPNCD,
    Importacao,
    LancamentoMensal,
    LevantamentoLIRAa,
    LogAuditoria,
    Modulo,
    OrigemDado,
    Perfil,
    Permissao,
    RegistroEpidemiologico,
    RelatorioQuadrimestral,
    StatusImportacao,
    StatusRelatorio,
    TipoValor,
    Usuario,
    quadrimestre_do_mes,
)

HOJE = date(2026, 11, 24)


# =====================================================================
# Modulo e Indicador – composição
# =====================================================================
class TestModuloIndicador:
    def test_modulo_cria_indicador_dentro_dele(self):
        sinan = Modulo("sinan", "Agravos")
        dengue = sinan.adicionar_indicador("dengue", "Dengue", "Arboviroses")
        assert sinan.sigla == "SINAN"
        assert dengue.codigo == "DENGUE"
        assert dengue.modulo is sinan

    def test_composicao_indicador_nao_pode_ser_trocado_de_modulo(self):
        sinan = Modulo("SINAN", "Agravos")
        dengue = sinan.adicionar_indicador("DENGUE", "Dengue", "Arboviroses")
        with pytest.raises(AttributeError):
            dengue.modulo = Modulo("LACEN", "Lab")

    def test_remover_indicador_do_modulo(self):
        sinan = Modulo("SINAN", "Agravos")
        sinan.adicionar_indicador("DENGUE", "Dengue", "Arboviroses")
        sinan.remover_indicador("DENGUE")
        assert len(sinan) == 0
        with pytest.raises(RegistroNaoEncontrado):
            sinan.obter_indicador("DENGUE")

    def test_codigo_repetido_no_modulo_e_recusado(self):
        sinan = Modulo("SINAN", "Agravos")
        sinan.adicionar_indicador("DENGUE", "Dengue", "Arboviroses")
        with pytest.raises(RegistroDuplicado):
            sinan.adicionar_indicador("dengue", "Outra dengue", "Arboviroses")

    def test_lista_de_indicadores_e_somente_leitura(self):
        sinan = Modulo("SINAN", "Agravos")
        sinan.adicionar_indicador("DENGUE", "Dengue", "Arboviroses")
        assert isinstance(sinan.indicadores, tuple)

    @pytest.mark.parametrize("sigla, nome", [("", "Agravos"), ("SINAN", "  ")])
    def test_modulo_exige_sigla_e_nome(self, sigla, nome):
        with pytest.raises(ErroValidacao):
            Modulo(sigla, nome)

    @pytest.mark.parametrize("codigo", ["", "COM ESPACO"])
    def test_codigo_de_indicador_invalido(self, codigo):
        with pytest.raises(ErroValidacao):
            Modulo("SINAN", "Agravos").adicionar_indicador(codigo, "Nome", "Grupo")

    def test_indicador_inativado_continua_no_modulo(self):
        sinan = Modulo("SINAN", "Agravos")
        dengue = sinan.adicionar_indicador("DENGUE", "Dengue", "Arboviroses")
        dengue.inativar()
        assert not dengue.ativo and "DENGUE" in sinan
        dengue.ativar()
        assert dengue.ativo

    def test_dunders_len_contains_str_repr(self):
        sinan = Modulo("SINAN", "Agravos")
        sinan.adicionar_indicador("DENGUE", "Dengue", "Arboviroses")
        sinan.adicionar_indicador("ZIKA", "Zika", "Arboviroses")
        assert len(sinan) == 2
        assert "dengue" in sinan and "FEBRE" not in sinan and 123 not in sinan
        assert str(sinan) == "SINAN – Agravos"
        assert repr(sinan) == "Modulo(sigla='SINAN', nome='Agravos', indicadores=2)"
        assert str(sinan.obter_indicador("DENGUE")) == "Dengue (SINAN)"
        assert "Indicador(codigo='DENGUE'" in repr(sinan.obter_indicador("DENGUE"))

    def test_indicadores_do_grupo(self):
        sinan = Modulo("SINAN", "Agravos")
        sinan.adicionar_indicador("DENGUE", "Dengue", "Arboviroses")
        sinan.adicionar_indicador("AIDS", "Aids", "IST/HIV/Aids")
        assert [i.codigo for i in sinan.indicadores_do_grupo("arboviroses")] == ["DENGUE"]


# =====================================================================
# Abstração, herança e polimorfismo
# =====================================================================
class TestHierarquiaRegistros:
    def test_classe_abstrata_nao_pode_ser_instanciada(self):
        with pytest.raises(TypeError):
            RegistroEpidemiologico(2026)

    def test_subclasse_incompleta_nao_pode_ser_instanciada(self):
        class RegistroIncompleto(RegistroEpidemiologico):
            def validar(self, hoje=None):
                return True

        with pytest.raises(TypeError):
            RegistroIncompleto(2026)

    def test_as_tres_classes_herdam_do_registro(self, dengue, endemias):
        registros = [
            LancamentoMensal(dengue, 2026, 5, 418),
            CicloPNCD(endemias, 2026, 3, 5, 40680, 40100),
            LevantamentoLIRAa(endemias, date(2026, 6, 29), date(2026, 7, 4), 0.2, 0.2),
        ]
        assert all(isinstance(r, RegistroEpidemiologico) for r in registros)

    def test_polimorfismo_resultado(self, dengue, endemias):
        """Mesma chamada resultado(), comportamento diferente em cada subclasse."""
        registros = [
            LancamentoMensal(dengue, 2026, 5, 418),
            CicloPNCD(endemias, 2026, 3, 5, 40680, 40100),
            LevantamentoLIRAa(endemias, date(2026, 6, 29), date(2026, 7, 4), 0.2, 0.2),
        ]
        assert [r.resultado() for r in registros] == [418, 98.57, "satisfatório"]

    def test_polimorfismo_validar(self, dengue, endemias):
        registros = [
            LancamentoMensal(dengue, 2026, 5, 418),
            CicloPNCD(endemias, 2026, 3, 5, 40680, 40100),
            LevantamentoLIRAa(endemias, date(2026, 6, 29), date(2026, 7, 4), 0.2, 0.2),
        ]
        assert all(r.validar(HOJE) for r in registros)

    def test_metodos_herdados_quadrimestre(self, dengue, endemias):
        assert LancamentoMensal(dengue, 2026, 5, 1).quadrimestre == 2
        assert CicloPNCD(endemias, 2026, 4, 8, 100, 50).quadrimestre == 3  # termina em setembro
        liraa = LevantamentoLIRAa(endemias, date(2026, 6, 29), date(2026, 7, 4), 0.2, 0.2)
        assert liraa.quadrimestre == 2
        assert liraa.pertence_ao_quadrimestre(2026, 2)

    @pytest.mark.parametrize("mes, quadrimestre", [(1, 1), (4, 1), (5, 2), (8, 2), (9, 3), (12, 3)])
    def test_rn10_quadrimestre_do_mes(self, mes, quadrimestre):
        assert quadrimestre_do_mes(mes) == quadrimestre

    def test_rn10_mes_invalido(self):
        with pytest.raises(ErroValidacao):
            quadrimestre_do_mes(13)

    @pytest.mark.parametrize("ano", [1999, 2101, "2026", True])
    def test_ano_invalido(self, dengue, ano):
        with pytest.raises(ErroValidacao):
            LancamentoMensal(dengue, ano, 5, 1)


# =====================================================================
# LancamentoMensal – encapsulamento e RN05
# =====================================================================
class TestLancamentoMensal:
    def test_criacao(self, dengue, digitador):
        lancamento = LancamentoMensal(dengue, 2026, 5, 418, registrado_por=digitador)
        assert (lancamento.indicador, lancamento.ano, lancamento.mes, lancamento.valor) == (dengue, 2026, 5, 418)
        assert lancamento.origem is OrigemDado.DIGITACAO
        assert lancamento.registrado_por is digitador
        assert isinstance(lancamento.criado_em, datetime)

    @pytest.mark.parametrize("valor", [-1, -3, "dez", None, True])
    def test_rn05_valor_invalido(self, dengue, valor):
        with pytest.raises(ErroValidacao):
            LancamentoMensal(dengue, 2026, 5, valor)

    def test_rn05_indicador_inteiro_recusa_decimal(self, dengue):
        with pytest.raises(ErroValidacao, match="inteiros"):
            LancamentoMensal(dengue, 2026, 5, 2.5)

    def test_float_inteiro_vira_int(self, dengue):
        assert LancamentoMensal(dengue, 2026, 5, 10.0).valor == 10
        assert isinstance(LancamentoMensal(dengue, 2026, 5, 10.0).valor, int)

    def test_a08_indicador_decimal_aceita_decimal(self):
        modulo = Modulo("TESTE", "Teste")
        taxa = modulo.adicionar_indicador("TAXA", "Taxa", "Grupo", TipoValor.DECIMAL)
        assert LancamentoMensal(taxa, 2026, 5, 2.5).valor == 2.5

    def test_setter_protege_alteracao_posterior(self, dengue):
        lancamento = LancamentoMensal(dengue, 2026, 5, 418)
        with pytest.raises(ErroValidacao):
            lancamento.valor = -1
        assert lancamento.valor == 418
        lancamento.valor = 420
        assert lancamento.valor == 420

    @pytest.mark.parametrize("mes", [0, 13, 5.0])
    def test_mes_invalido(self, dengue, mes):
        with pytest.raises(ErroValidacao):
            LancamentoMensal(dengue, 2026, mes, 1)

    def test_rn05_mes_nao_encerrado(self, dengue):
        with pytest.raises(ErroValidacao, match="ainda não terminou"):
            LancamentoMensal(dengue, 2026, 11, 1).validar(HOJE)

    def test_indicador_inativo_nao_recebe_lancamento(self, dengue):
        dengue.inativar()
        with pytest.raises(ErroValidacao, match="inativo"):
            LancamentoMensal(dengue, 2026, 5, 1).validar(HOJE)

    def test_eq_e_hash_pela_chave_rn04(self, dengue):
        a = LancamentoMensal(dengue, 2026, 5, 418)
        b = LancamentoMensal(dengue, 2026, 5, 1)
        c = LancamentoMensal(dengue, 2026, 6, 418)
        assert a == b and a != c
        assert len({a, b, c}) == 2
        assert a.__eq__("texto") is NotImplemented

    def test_str_repr(self, dengue):
        lancamento = LancamentoMensal(dengue, 2026, 5, 418)
        assert str(lancamento) == "Dengue – 05/2026: 418"
        assert repr(lancamento) == "LancamentoMensal(indicador='DENGUE', ano=2026, mes=5, valor=418)"


# =====================================================================
# CicloPNCD – RN08
# =====================================================================
class TestCicloPNCD:
    def test_rn08_cobertura(self, endemias):
        assert CicloPNCD(endemias, 2026, 3, 5, 40680, 40100).cobertura() == 98.57

    def test_mes_final_bimestral(self, endemias):
        assert CicloPNCD(endemias, 2026, 3, 5, 100, 1).mes_final == 6

    @pytest.mark.parametrize(
        "numero, mes_inicial, programados, trabalhados",
        [(0, 5, 100, 1), (7, 5, 100, 1), (3, 12, 100, 1), (3, 5, 0, 0), (3, 5, 100, -1)],
    )
    def test_dados_invalidos(self, endemias, numero, mes_inicial, programados, trabalhados):
        with pytest.raises(ErroValidacao):
            CicloPNCD(endemias, 2026, numero, mes_inicial, programados, trabalhados)

    def test_trabalhados_maior_que_programados(self, endemias):
        """O protótipo mostrava 57.000 imóveis trabalhados para 40.680 programados."""
        with pytest.raises(ErroValidacao, match="maior que os programados"):
            CicloPNCD(endemias, 2026, 3, 5, 40680, 57000)

    def test_programados_nao_pode_ficar_menor_que_trabalhados(self, endemias):
        ciclo = CicloPNCD(endemias, 2026, 3, 5, 40680, 40100)
        with pytest.raises(ErroValidacao):
            ciclo.imoveis_programados = 100

    def test_ciclo_nao_encerrado(self, endemias):
        with pytest.raises(ErroValidacao):
            CicloPNCD(endemias, 2026, 6, 10, 100, 10).validar(HOJE)

    def test_chave_str_repr(self, endemias):
        ciclo = CicloPNCD(endemias, 2026, 3, 5, 40680, 40100)
        assert ciclo.chave() == ("PNCD", 2026, 3)
        assert "98,57%" in str(ciclo)
        assert repr(ciclo).startswith("CicloPNCD(ano=2026, numero=3")


# =====================================================================
# LevantamentoLIRAa – RN09
# =====================================================================
class TestLevantamentoLIRAa:
    @pytest.mark.parametrize(
        "iip, risco",
        [(0, "satisfatório"), (0.99, "satisfatório"), (1, "alerta"), (3.9, "alerta"), (4, "risco"), (7.5, "risco")],
    )
    def test_rn09_classificacao(self, endemias, iip, risco):
        liraa = LevantamentoLIRAa(endemias, date(2026, 6, 29), date(2026, 7, 4), iip, 0)
        assert liraa.classificar_risco() == risco

    def test_a08_indices_decimais_aceitos(self, endemias):
        liraa = LevantamentoLIRAa(endemias, date(2026, 6, 29), date(2026, 7, 4), 0.2, 0.2, 171)
        assert (liraa.indice_predial, liraa.indice_breteau, liraa.pontos_estrategicos) == (0.2, 0.2, 171)
        assert liraa.ano == 2026

    def test_data_final_antes_da_inicial(self, endemias):
        with pytest.raises(ErroValidacao):
            LevantamentoLIRAa(endemias, date(2026, 7, 4), date(2026, 6, 29), 0.2, 0.2)

    def test_datas_obrigatorias(self, endemias):
        with pytest.raises(ErroValidacao):
            LevantamentoLIRAa(endemias, None, date(2026, 6, 29), 0.2, 0.2)

    @pytest.mark.parametrize("iip, ib, pontos", [(-0.1, 0, 0), (0, -1, 0), (0, 0, -1), ("x", 0, 0)])
    def test_indices_invalidos(self, endemias, iip, ib, pontos):
        with pytest.raises(ErroValidacao):
            LevantamentoLIRAa(endemias, date(2026, 6, 29), date(2026, 7, 4), iip, ib, pontos)

    def test_levantamento_nao_encerrado(self, endemias):
        with pytest.raises(ErroValidacao):
            LevantamentoLIRAa(endemias, date(2026, 11, 20), date(2026, 11, 30), 1, 1).validar(HOJE)

    def test_str(self, endemias):
        liraa = LevantamentoLIRAa(endemias, date(2026, 6, 29), date(2026, 7, 4), 0.2, 0.2)
        assert str(liraa) == "LIRAa 29/06/2026–04/07/2026: IIP 0,2 / IB 0,2 – satisfatório"
        assert liraa.chave() == ("LIRAA", "2026-06-29")
        assert "LevantamentoLIRAa(" in repr(liraa)


# =====================================================================
# Usuario, Perfil, Permissao – agregação, encapsulamento, RNF05
# =====================================================================
class TestUsuarioPerfil:
    def test_agregacao_mesma_permissao_em_varios_perfis(self):
        painel = Permissao(Permissao.VER_PAINEL)
        gestor = Perfil("Gestor", permissoes=[painel])
        coordenador = Perfil("Coordenador", permissoes=[painel, Permissao(Permissao.HOMOLOGAR_RELATORIO)])
        assert painel in gestor.permissoes and painel in coordenador.permissoes
        del gestor  # a permissão continua existindo no outro perfil
        assert Permissao.VER_PAINEL in coordenador

    def test_perfil_sem_repeticao_de_permissao(self):
        perfil = Perfil("X", permissoes=[Permissao("a"), Permissao("A")])
        assert len(perfil.permissoes) == 1

    def test_perfil_so_aceita_permissao(self):
        with pytest.raises(ErroValidacao):
            Perfil("X").adicionar_permissao("ver_painel")

    def test_remover_permissao(self):
        p = Permissao("ver_painel")
        perfil = Perfil("X", permissoes=[p])
        perfil.remover_permissao(p)
        assert not perfil.possui("ver_painel")

    def test_validacoes_de_permissao_e_perfil(self):
        with pytest.raises(ErroValidacao):
            Permissao("")
        with pytest.raises(ErroValidacao):
            Perfil("")

    def test_permissao_dunders(self):
        p = Permissao("VER_PAINEL", "Ver painel")
        assert p == Permissao("ver_painel") and p.codigo == "ver_painel"
        assert str(p) == "Ver painel" and repr(p) == "Permissao(codigo='ver_painel')"
        assert p.__eq__(1) is NotImplemented
        assert "ver_painel" in repr(Perfil("Gestor", permissoes=[p])) and str(Perfil("Gestor")) == "Gestor"

    def test_rnf05_senha_guardada_como_hash(self, repo):
        usuario = Usuario("Ana", "ana", repo.obter_perfil("Gestor"), senha="minhasenha")
        assert "minhasenha" not in usuario.senha_hash
        assert usuario.autenticar("minhasenha")
        assert not usuario.autenticar("errada")

    def test_rnf05_atributo_senha_e_privado(self, repo):
        usuario = Usuario("Ana", "ana", repo.obter_perfil("Gestor"), senha="minhasenha")
        with pytest.raises(AttributeError):
            usuario.__senha_hash  # noqa: B018 – name mangling impede o acesso direto
        with pytest.raises(AttributeError):
            usuario.senha_hash = "x"

    def test_rnf05_senha_curta(self, repo):
        with pytest.raises(ErroValidacao, match="8 caracteres"):
            Usuario("Ana", "ana", repo.obter_perfil("Gestor"), senha="1234567")

    def test_usuario_sem_senha(self, repo):
        with pytest.raises(ErroValidacao):
            Usuario("Ana", "ana", repo.obter_perfil("Gestor"))

    def test_hash_diferente_para_mesma_senha(self, repo):
        """O 'sal' aleatório faz dois hashes da mesma senha serem diferentes."""
        perfil = repo.obter_perfil("Gestor")
        assert Usuario("A", "a", perfil, senha="igual1234").senha_hash != \
            Usuario("B", "b", perfil, senha="igual1234").senha_hash

    def test_autenticar_atualiza_ultimo_acesso(self, repo):
        usuario = Usuario("Ana", "ana", repo.obter_perfil("Gestor"), senha="minhasenha")
        assert usuario.ultimo_acesso is None
        usuario.autenticar("minhasenha")
        assert usuario.ultimo_acesso is not None

    def test_usuario_inativo_nao_autentica_nem_tem_permissao(self, gestor):
        gestor.inativar()
        assert not gestor.autenticar("senha1234")
        assert not gestor.tem_permissao(Permissao.VER_PAINEL)

    @pytest.mark.parametrize("login", ["", "com espaco"])
    def test_login_invalido(self, repo, login):
        with pytest.raises(ErroValidacao):
            Usuario("Ana", login, repo.obter_perfil("Gestor"), senha="minhasenha")

    def test_nome_e_perfil_obrigatorios(self, repo):
        with pytest.raises(ErroValidacao):
            Usuario(" ", "ana", repo.obter_perfil("Gestor"), senha="minhasenha")
        with pytest.raises(ErroValidacao):
            Usuario("Ana", "ana", "Gestor", senha="minhasenha")

    def test_eq_hash_pelo_login(self, repo):
        perfil = repo.obter_perfil("Gestor")
        a = Usuario("Ana", "ANA", perfil, senha="minhasenha")
        b = Usuario("Ana Maria", "ana", repo.obter_perfil("Digitador"), senha="outrasenha")
        assert a == b and hash(a) == hash(b) and len({a, b}) == 1
        assert a.__eq__("ana") is NotImplemented

    def test_str_repr_nao_mostram_senha(self, gestor):
        assert str(gestor) == "Gestor (gestor) – Gestor, ativo"
        assert repr(gestor) == "Usuario(login='gestor', perfil='Gestor', ativo=True)"
        assert "hash" not in repr(gestor)

    def test_permissoes_por_perfil_quadro3_srs(self, digitador, gestor, coordenador, admin):
        assert digitador.tem_permissao(Permissao.LANCAR_DADOS)
        assert not gestor.tem_permissao(Permissao.LANCAR_DADOS)
        assert coordenador.tem_permissao(Permissao.HOMOLOGAR_RELATORIO)
        assert not gestor.tem_permissao(Permissao.HOMOLOGAR_RELATORIO)
        assert admin.tem_permissao(Permissao.GERENCIAR_USUARIOS)
        assert not admin.tem_permissao(Permissao.VER_PAINEL)

    def test_coordenador_herda_permissoes_do_gestor(self, gestor, coordenador):
        """Generalização Coordenador → Gestor do diagrama de casos de uso."""
        assert gestor.perfil.permissoes < coordenador.perfil.permissoes


# =====================================================================
# Importacao
# =====================================================================
class TestImportacao:
    def test_len_conta_validas_e_rejeitadas(self):
        imp = Importacao("lote.csv")
        imp.adicionar_valida({"codigo": "DENGUE"})
        imp.adicionar_valida({"codigo": "ZIKA"})
        imp.adicionar_rejeitada(4, "valor negativo")
        assert len(imp) == 3
        assert (imp.linhas_validas, imp.linhas_rejeitadas) == (2, 1)
        assert imp.erros == ((4, "valor negativo"),)

    def test_fluxo_de_status(self):
        imp = Importacao("lote.csv")
        assert imp.status is StatusImportacao.PENDENTE
        imp.adicionar_valida({"a": 1})
        imp.confirmar()
        assert imp.status is StatusImportacao.CONFIRMADA
        with pytest.raises(ErroValidacao):
            imp.adicionar_valida({"b": 2})
        with pytest.raises(ErroValidacao):
            imp.cancelar()

    def test_nao_confirma_sem_linhas_validas(self):
        with pytest.raises(ErroValidacao):
            Importacao("vazio.csv").confirmar()

    def test_cancelar(self):
        imp = Importacao("lote.csv")
        imp.cancelar()
        assert imp.status is StatusImportacao.CANCELADA

    def test_validas_e_copia(self):
        imp = Importacao("lote.csv")
        imp.adicionar_valida({"a": 1})
        imp.validas[0]["a"] = 999
        assert imp.validas[0]["a"] == 1

    def test_nome_obrigatorio_e_str(self):
        with pytest.raises(ErroValidacao):
            Importacao(" ")
        imp = Importacao("lote.csv")
        assert str(imp) == "lote.csv: 0 válidas, 0 com erro (pendente)"
        assert repr(imp).startswith("Importacao(nome_arquivo='lote.csv'")


# =====================================================================
# RelatorioQuadrimestral – RF14, RN11, RN06
# =====================================================================
class TestRelatorio:
    def test_meses_rn10(self):
        assert list(RelatorioQuadrimestral(2026, 2).meses) == [5, 6, 7, 8]
        assert list(RelatorioQuadrimestral(2026, 3).meses) == [9, 10, 11, 12]

    @pytest.mark.parametrize("ano, quad", [(2026, 0), (2026, 4), (1990, 1)])
    def test_periodo_invalido(self, ano, quad):
        with pytest.raises(ErroValidacao):
            RelatorioQuadrimestral(ano, quad)

    def test_homologar_e_reabrir(self, coordenador):
        relatorio = RelatorioQuadrimestral(2026, 2)
        relatorio.homologar(coordenador, datetime(2026, 11, 24, 10, 0))
        assert relatorio.esta_bloqueado and relatorio.status is StatusRelatorio.HOMOLOGADO
        assert relatorio.homologado_por == "coordenador"
        assert relatorio.homologado_em == datetime(2026, 11, 24, 10, 0)
        relatorio.reabrir(coordenador, "Correção dos dados de dengue de junho")
        assert relatorio.status is StatusRelatorio.REABERTO and relatorio.versao == 2
        assert relatorio.justificativas == ("Correção dos dados de dengue de junho",)

    def test_so_coordenador_homologa(self, gestor, digitador):
        for usuario in (gestor, digitador):
            with pytest.raises(AcessoNegado):
                RelatorioQuadrimestral(2026, 2).homologar(usuario)

    def test_nao_homologa_duas_vezes(self, coordenador):
        relatorio = RelatorioQuadrimestral(2026, 2)
        relatorio.homologar(coordenador)
        with pytest.raises(ErroValidacao):
            relatorio.homologar(coordenador)

    def test_rn11_reabertura_exige_justificativa(self, coordenador):
        relatorio = RelatorioQuadrimestral(2026, 2)
        relatorio.homologar(coordenador)
        with pytest.raises(ErroValidacao, match="justificativa"):
            relatorio.reabrir(coordenador, "curta")

    def test_so_reabre_homologado(self, coordenador):
        with pytest.raises(ErroValidacao):
            RelatorioQuadrimestral(2026, 2).reabrir(coordenador, "justificativa longa o bastante")

    def test_rn06_consolidar_soma_so_o_quadrimestre(self, dengue):
        lancamentos = [LancamentoMensal(dengue, 2026, m, v) for m, v in [(5, 418), (6, 380), (9, 50)]]
        lancamentos.append(LancamentoMensal(dengue, 2025, 5, 999))
        assert RelatorioQuadrimestral(2026, 2).consolidar(lancamentos) == {"DENGUE": 798}

    def test_str_repr(self):
        relatorio = RelatorioQuadrimestral(2026, 2)
        assert str(relatorio) == "2º quadrimestre/2026 – rascunho (v1)"
        assert repr(relatorio) == "RelatorioQuadrimestral(ano=2026, quadrimestre=2, status='rascunho', versao=1)"


# =====================================================================
# LogAuditoria – RNF10
# =====================================================================
class TestLogAuditoria:
    def test_log_e_imutavel(self):
        log = LogAuditoria("digitador", "incluir", "LancamentoMensal", None, "Dengue – 05/2026: 418")
        with pytest.raises(AttributeError):
            log.acao = "excluir"

    def test_usuario_e_acao_obrigatorios(self):
        with pytest.raises(ErroValidacao):
            LogAuditoria("", "incluir", "X")

    def test_str(self):
        log = LogAuditoria("coord", "homologar", "Relatório", "rascunho", "homologado",
                           datetime(2026, 11, 24, 10, 0))
        assert str(log) == "[24/11/2026 10:00] coord – homologar – Relatório (rascunho → homologado)"
        assert str(LogAuditoria("x", "login", "Sessao", data_hora=datetime(2026, 1, 1))).endswith("Sessao")
        assert repr(log) == "LogAuditoria(usuario='coord', acao='homologar', entidade='Relatório')"
