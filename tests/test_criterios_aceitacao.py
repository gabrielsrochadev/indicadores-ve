"""Um teste para cada critério de aceitação da SRS (seção 12), com o mesmo
identificador (CA01 = RF01 … CA14 = RF14).

Os testes usam os DADOS REAIS do relatório do 2º quadrimestre de 2026
(fixture sistema_real), exceto onde o próprio critério usa outro valor.
"""

from __future__ import annotations

import csv
import time
from datetime import date

import pytest

from indicadores_ve.excecoes import (
    AcessoNegado,
    DadoPessoalDetectado,
    ErroAutenticacao,
    ErroValidacao,
    PeriodoHomologado,
)
from indicadores_ve.models import CicloPNCD, LancamentoMensal, LevantamentoLIRAa
from indicadores_ve.services import Periodo

Q2_2026 = Periodo.quadrimestre(2026, 2)
Q2_2025 = Periodo.quadrimestre(2025, 2)


def usuario(sistema, login):
    return sistema.repositorio.obter_usuario(login)


def test_ca01_rf01_registrar_notificacao_sinan(sistema, digitador):
    """RF01: o Digitador registra Dengue = 418 em maio/2026 e o valor aparece no total."""
    sistema.lancamentos.lancar_valor(digitador, "DENGUE", 2026, 5, 418)
    assert sistema.indicadores.total_indicador("DENGUE", Q2_2026) == 418


def test_ca02_rf02_registrar_exames_lacen(sistema_real):
    """RF02: Tuberculose TRM mai.–ago. (6, 8, 8, 12) totaliza 34."""
    assert sistema_real.indicadores.total_indicador("LAC_TB_TRM", Q2_2026) == 34


def test_ca02_rf02_producao_do_laboratorio_da_ve(sistema_real):
    assert sistema_real.indicadores.total_indicador("LAB_CARGA_VIRAL_HIV", Q2_2026) == 254


def test_ca03_rf03_pncd_e_liraa(sistema, digitador, endemias):
    """RF03 / RN08 / RN09: 40.100 de 40.680 imóveis = 98,57%; IIP 0,2 = satisfatório."""
    ciclo = sistema.lancamentos.registrar(digitador, CicloPNCD(endemias, 2026, 3, 5, 40680, 40100))
    liraa = sistema.lancamentos.registrar(
        digitador, LevantamentoLIRAa(endemias, date(2026, 6, 29), date(2026, 7, 4), 0.2, 0.2, 171)
    )
    assert ciclo.cobertura() == 98.57
    assert liraa.classificar_risco() == "satisfatório"


def test_ca04_rf04_dados_vitais_comparados_ao_ano_anterior(sistema_real):
    """RF04: nascidos vivos 557 (2026) × 598 (2025) e total de óbitos 176 × 220."""
    gestor = usuario(sistema_real, "gestor")
    linhas = {l.codigo: l for l in sistema_real.indicadores.comparar(
        gestor, Periodo.mes(2026, 8), Periodo.mes(2025, 8), modulo="SIM_SINASC")}
    assert (linhas["NASCIDOS_VIVOS"].valor_atual, linhas["NASCIDOS_VIVOS"].valor_base) == (557, 598)
    assert (linhas["OBITOS_TOTAL"].valor_atual, linhas["OBITOS_TOTAL"].valor_base) == (176, 220)
    assert linhas["OBITOS_TOTAL"].variacao == -20.0


def test_ca05_rf05_painel_abre_no_ultimo_quadrimestre(sistema_real):
    """RF05: o painel do Gestor abre no último quadrimestre com dados e mostra os totais."""
    painel = sistema_real.indicadores.painel(usuario(sistema_real, "gestor"))
    cartoes = {c.titulo: c for c in painel.cartoes}
    assert painel.periodo == Q2_2026
    assert cartoes["Notificações (SINAN)"].valor == 2054
    assert cartoes["Nascidos vivos (SINASC)"].variacao == -6.9
    assert cartoes["Cobertura PNCD (último ciclo)"].valor == "98,57%"
    assert painel.principais_agravos[0] == ("Dengue", 1191)


def test_ca05_rnf03_painel_em_ate_3_segundos(sistema_real):
    """RF05 / RNF03: painel e comparativo prontos em até 3 segundos com os dados reais."""
    gestor = usuario(sistema_real, "gestor")
    inicio = time.perf_counter()
    sistema_real.indicadores.painel(gestor)
    sistema_real.indicadores.comparar(gestor, Q2_2026, Q2_2025)
    assert time.perf_counter() - inicio < 3


def test_ca06_rf06_comparativo_entre_periodos(sistema, digitador, coordenador):
    """RF06 / RN07: Dengue 1.191 (2026) × 1.000 (2025) → diferença 191 e variação +19,1%."""
    sistema.lancamentos.lancar_valor(digitador, "DENGUE", 2026, 5, 1191)
    sistema.lancamentos.lancar_valor(digitador, "DENGUE", 2025, 5, 1000)
    linha = sistema.indicadores.comparar(coordenador, Q2_2026, Q2_2025, codigo="DENGUE")[0]
    assert linha.diferenca == 191
    assert sistema.indicadores.formatar_variacao(linha.variacao) == "+19,1%"


def test_ca07_rf07_filtro_por_grupo(sistema_real):
    """RF07: o filtro 'Arboviroses' traz só Dengue, Chikungunya e Zika."""
    codigos = {i.codigo for i in sistema_real.indicadores.filtrar_indicadores(grupo="Arboviroses")}
    assert codigos == {"DENGUE", "CHIKUNGUNYA", "ZIKA"}


def test_ca07_rf07_filtro_por_sistema_de_origem(sistema_real):
    assert len(sistema_real.indicadores.filtrar_indicadores(modulo="SINAN")) == 29


def test_ca08_rf08_exportacao_igual_a_tela_com_cabecalho(sistema_real, tmp_path):
    """RF08: o arquivo exportado traz cabeçalho, período, emissão, situação e os mesmos valores da tela."""
    gestor = usuario(sistema_real, "gestor")
    caminho = sistema_real.relatorios.exportar(gestor, 2026, 2, "csv", tmp_path)
    linhas = list(csv.reader(caminho.open(encoding="utf-8-sig"), delimiter=";"))
    cabecalho = " ".join(l[0] for l in linhas[:5])
    assert "Secretaria Municipal de Saúde de Balsas-MA" in cabecalho
    assert "2º quadrimestre de 2026" in cabecalho and "Emitido em 24/11/2026" in cabecalho
    assert "Situação: RASCUNHO" in cabecalho
    dengue = next(l for l in linhas if l and l[0] == "Dengue")
    assert dengue[1:] == ["418", "380", "237", "156", "1191"]
    assert dengue[-1] == str(sistema_real.indicadores.total_indicador("DENGUE", Q2_2026))


def test_ca09_rf09_gestor_nao_acessa_lancamento(sistema, gestor):
    """RF09: o Gestor que tenta lançar dados recebe acesso negado."""
    with pytest.raises(AcessoNegado, match="Acesso negado"):
        sistema.lancamentos.lancar_valor(gestor, "DENGUE", 2026, 5, 418)


def test_ca10_rf10_usuario_inativo_nao_entra(sistema, admin):
    """RF10: usuário inativado pelo Administrador não consegue entrar."""
    sistema.usuarios.inativar(admin, "digitador")
    with pytest.raises(ErroAutenticacao, match="inativo"):
        sistema.autenticacao.entrar("digitador", "senha1234")


def test_ca11_rf11_importar_120_linhas(sistema, digitador):
    """RF11: planilha com 120 linhas válidas → prévia com 120 linhas e 120 gravadas."""
    codigos = [("SINAN", c) for c in ("DENGUE", "CHIKUNGUNYA", "ZIKA", "SIFILIS_ADULTO")] + [("LACEN", "LAC_TB_TRM")]
    linhas = ["modulo;codigo_indicador;ano;mes;valor"]
    for ano in (2024, 2025):
        for modulo, codigo in codigos:
            for mes in range(1, 13):
                linhas.append(f"{modulo};{codigo};{ano};{mes};{mes * 3}")
    assert len(linhas) - 1 == 120
    importacao = sistema.importacao.pre_visualizar(digitador, "\n".join(linhas), "historico.csv")
    assert len(importacao) == 120 and importacao.linhas_validas == 120
    resumo = sistema.importacao.confirmar(digitador, importacao.id)
    assert resumo == {"inseridos": 120, "substituidos": 0, "rejeitados": 0}
    assert len(sistema.repositorio.lancamentos()) == 120


def test_ca12_rf12_valor_negativo_rejeitado(dengue):
    """RF12 / RN05: valor −3 é rejeitado com mensagem clara."""
    with pytest.raises(ErroValidacao, match="não pode ser negativo"):
        LancamentoMensal(dengue, 2026, 6, -3)


def test_ca12_rf12_rn01_coluna_de_dado_pessoal_rejeitada(sistema, digitador):
    """RF12 / RN01: planilha com nome de paciente é recusada inteira (LGPD)."""
    with pytest.raises(DadoPessoalDetectado):
        sistema.importacao.pre_visualizar(
            digitador, "nome_paciente;modulo;codigo_indicador;ano;mes;valor\nFulano;SINAN;DENGUE;2026;6;1\n"
        )


def test_ca13_rf13_totais_recalculados_automaticamente(sistema_real):
    """RF13 / RN06: corrigir um mês atualiza o total do quadrimestre e o painel."""
    dig = usuario(sistema_real, "digitador")
    gestor = usuario(sistema_real, "gestor")
    sistema_real.lancamentos.lancar_valor(dig, "DENGUE", 2026, 6, 400, confirmar_substituicao=True)
    assert sistema_real.indicadores.total_indicador("DENGUE", Q2_2026) == 1191 + 20
    cartoes = {c.titulo: c.valor for c in sistema_real.indicadores.painel(gestor).cartoes}
    assert cartoes["Notificações (SINAN)"] == 2054 + 20


def test_ca14_rf14_periodo_homologado_bloqueia_alteracoes(sistema_real):
    """RF14 / RN11: depois de homologado, o quadrimestre não aceita alteração."""
    coord = usuario(sistema_real, "coordenador")
    dig = usuario(sistema_real, "digitador")
    sistema_real.relatorios.homologar(coord, 2026, 2)
    with pytest.raises(PeriodoHomologado):
        sistema_real.lancamentos.lancar_valor(dig, "DENGUE", 2026, 6, 1, confirmar_substituicao=True)
    assert sistema_real.indicadores.total_indicador("DENGUE", Q2_2026) == 1191
