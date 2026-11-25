"""Testes da interface no terminal com um usuário simulado.

O SimuladorTerminal entrega as respostas da lista, uma por pergunta, e
guarda tudo o que o sistema imprimiu. Quando as respostas acabam, ele se
comporta como o terminal fechado (EOFError), e o programa termina.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from indicadores_ve.__main__ import main
from indicadores_ve.cli import Aplicacao, Console
from indicadores_ve.persistence import RepositorioJSON
from indicadores_ve.services import Periodo

from conftest import DADOS_INICIAIS, RAIZ, SENHA


class SimuladorTerminal:
    def __init__(self, respostas: list[str]) -> None:
        self.respostas = list(respostas)
        self.saida: list[str] = []

    def entrada(self, pergunta: str) -> str:
        self.saida.append(pergunta)
        if not self.respostas:
            raise EOFError
        return self.respostas.pop(0)

    def escrever(self, texto: str) -> None:
        self.saida.append(texto)

    @property
    def texto(self) -> str:
        return "\n".join(self.saida)


def rodar(sistema, respostas, tmp_path=None) -> SimuladorTerminal:
    terminal = SimuladorTerminal(respostas)
    console = Console(entrada=terminal.entrada, saida=terminal.escrever)
    Aplicacao(sistema, console, pasta_exportacao=tmp_path or "exportacoes").executar()
    return terminal


# =====================================================================
# Login e menu por perfil – RF09
# =====================================================================
def test_login_errado_e_depois_certo(sistema):
    t = rodar(sistema, ["digitador", "errada", "digitador", SENHA, "0", ""])
    assert "Login ou senha inválidos" in t.texto
    assert "Bem-vindo(a), Técnico – perfil Digitador" in t.texto


@pytest.mark.parametrize(
    "login, aparece, nao_aparece",
    [
        ("digitador", "Lançar total mensal", "Homologar"),
        ("gestor", "Exportar relatório", "Lançar total mensal"),
        ("coordenador", "Homologar / reabrir quadrimestre", "Importar planilha"),
        ("admin", "Gerenciar usuários", "Painel epidemiológico"),
    ],
)
def test_menu_mostra_so_o_que_o_perfil_pode(sistema, login, aparece, nao_aparece):
    t = rodar(sistema, [login, SENHA, "0", ""])
    assert aparece in t.texto and nao_aparece not in t.texto


def test_rnf05_sessao_expirada_volta_ao_login(sistema, relogio, digitador):
    sistema.lancamentos.lancar_valor(digitador, "DENGUE", 2026, 5, 418)
    terminal = SimuladorTerminal(["gestor", SENHA])
    app = Aplicacao(sistema, Console(entrada=terminal.entrada, saida=terminal.escrever))
    app.entrar()
    relogio.avancar(minutes=31)
    terminal.respostas = ["1"]
    app.menu_principal()
    assert "Sessão expirada" in terminal.texto and app.sessao is None


def test_terminal_fechado_encerra_sem_erro(sistema):
    assert "Encerrando" in rodar(sistema, ["digitador"]).texto


# =====================================================================
# Lançamentos – RF01, RN04, RF12
# =====================================================================
def test_lancar_e_substituir_com_confirmacao(sistema):
    respostas = ["digitador", SENHA,
                 "4", "1", "dengue", "1", "2026", "5", "418",
                 "4", "1", "dengue", "1", "2026", "5", "420", "s",
                 "0", ""]
    t = rodar(sistema, respostas)
    assert "Registrado: Dengue – 05/2026: 418" in t.texto
    assert "Confirme a substituição" in t.texto
    assert "Registrado: Dengue – 05/2026: 420" in t.texto
    assert sistema.indicadores.total_indicador("DENGUE", Periodo.mes(2026, 5)) == 420


def test_recusar_substituicao_nao_altera(sistema):
    respostas = ["digitador", SENHA,
                 "4", "1", "dengue", "1", "2026", "5", "418",
                 "4", "1", "dengue", "1", "2026", "5", "999", "n",
                 "0", ""]
    t = rodar(sistema, respostas)
    assert "Nada foi alterado" in t.texto
    assert sistema.indicadores.total_indicador("DENGUE", Periodo.mes(2026, 5)) == 418


def test_entradas_invalidas_sao_perguntadas_de_novo(sistema):
    respostas = ["digitador", SENHA,
                 "99",                                  # opção inexistente
                 "4", "1", "xpto",                      # busca sem resultado → volta ao menu
                 "4", "1", "dengue", "abc", "1",        # indicador inválido, depois válido
                 "1999", "2026", "13", "5", "-3",       # ano e mês fora da faixa; valor negativo
                 "0", ""]
    t = rodar(sistema, respostas)
    assert "no máximo" in t.texto                       # opção 99
    assert "Nenhum indicador encontrado" in t.texto     # busca sem resultado
    assert "Escolha um número de 1 a 1" in t.texto      # indicador 'abc'
    assert "no mínimo 2000" in t.texto
    assert "não pode ser negativo" in t.texto           # RN05 vinda da classe


def test_registrar_ciclo_e_liraa(sistema):
    respostas = ["digitador", SENHA,
                 "5", "2026", "3", "5", "40680", "40100",
                 "6", "31/02/2026", "29/06/2026", "04/07/2026", "0,2", "0,2", "171",
                 "0", ""]
    t = rodar(sistema, respostas)
    assert "98,57%" in t.texto
    assert "Data inválida" in t.texto
    assert "Classificação de risco (RN09): satisfatório" in t.texto


# =====================================================================
# Importação – RF11
# =====================================================================
def test_importar_com_previa_e_confirmacao(sistema_real):
    exemplo = str(RAIZ / "data" / "exemplo_importacao.csv")
    t = rodar(sistema_real, ["digitador", "digit2026", "7", exemplo, "s", "0", ""])
    assert "Linhas válidas: 6" in t.texto and "Linhas com erro: 2" in t.texto
    assert "linha 7: O valor não pode ser negativo." in t.texto
    assert "6 inseridos, 0 substituídos, 2 rejeitados" in t.texto


def test_importar_e_desistir(sistema):
    exemplo = str(RAIZ / "data" / "exemplo_importacao.csv")
    t = rodar(sistema, ["digitador", SENHA, "7", exemplo, "n", "0", ""])
    assert "Nada foi gravado" in t.texto and sistema.repositorio.lancamentos() == []


def test_importar_arquivo_com_dado_pessoal(sistema):
    exemplo = str(RAIZ / "data" / "exemplo_rejeitado_lgpd.csv")
    t = rodar(sistema, ["digitador", SENHA, "7", exemplo, "0", ""])
    assert "LGPD" in t.texto and "nome_paciente" in t.texto


def test_importar_arquivo_inexistente(sistema):
    t = rodar(sistema, ["digitador", SENHA, "7", "nao_existe.csv", "0", ""])
    assert "Arquivo não encontrado" in t.texto


# =====================================================================
# Painel, comparativo e consulta – RF05, RF06, RF07
# =====================================================================
def test_painel_comparativo_e_consulta_com_dados_reais(sistema_real):
    respostas = ["gestor", "gestor2026",
                 "1", "", "",
                 "2", "2", "2026", "2", "s", "3", "",
                 "3", "", "", "1", "",
                 "0", ""]
    t = rodar(sistema_real, respostas)
    assert "Painel epidemiológico – 2º quadrimestre/2026" in t.texto
    assert "2.054" in t.texto and "-6,9%" in t.texto and "█" in t.texto
    assert "Comparativo: 2º quadrimestre/2026 × 2º quadrimestre/2025" in t.texto and "-20,0%" in t.texto
    assert "Total calculado pelo sistema (RN06): 2.054" in t.texto


# =====================================================================
# Homologação, exportação, usuários e auditoria – RF08, RF10, RF14
# =====================================================================
def test_homologar_exportar_e_reabrir(sistema_real, tmp_path):
    respostas = ["coordenador", "coord2026",
                 "4", "2026", "2", "s",
                 "5", "2026", "2", "1",
                 "4", "2026", "2", "s", "Correção do total de dengue",
                 "0", ""]
    t = rodar(sistema_real, respostas, tmp_path)
    assert "2º quadrimestre/2026 homologado" in t.texto
    assert (tmp_path / "relatorio_2026_Q2_v1.csv").exists()
    assert "Período reaberto" in t.texto
    assert sistema_real.repositorio.obter_relatorio(2026, 2).versao == 2


def test_digitador_bloqueado_depois_da_homologacao(sistema_real):
    sistema_real.relatorios.homologar(sistema_real.repositorio.obter_usuario("coordenador"), 2026, 2)
    t = rodar(sistema_real, ["digitador", "digit2026", "4", "1", "dengue", "1", "2026", "6", "5", "0", ""])
    assert "está homologado" in t.texto


def test_admin_cadastra_inativa_e_ve_auditoria(sistema):
    respostas = ["admin", SENHA,
                 "1", "1", "Maria Técnica", "maria", "senhasegura", "1",
                 "1", "2", "maria",
                 "1", "3", "maria",
                 "1", "4", "maria", "outrasenha1",
                 "1", "5", "maria", "2",
                 "1", "6",
                 "2", "0", ""]
    t = rodar(sistema, respostas)
    assert "Cadastrado: Maria Técnica (maria) – Digitador, ativo" in t.texto
    assert "Inativado:" in t.texto and "Reativado:" in t.texto and "Senha redefinida" in t.texto
    assert "Alterado: Maria Técnica (maria) – Gestor" in t.texto
    assert "admin – incluir – Usuario maria" in t.texto


# =====================================================================
# Pontos de entrada
# =====================================================================
def test_main_cria_banco_na_primeira_execucao(tmp_path, monkeypatch):
    def terminal_fechado(_):
        raise EOFError

    monkeypatch.setattr("builtins.input", terminal_fechado)
    banco = tmp_path / "banco.json"
    assert main(["--banco", str(banco), "--dados", str(DADOS_INICIAIS)]) == 0
    repositorio = RepositorioJSON(banco)
    repositorio.carregar()
    assert len(repositorio.listar_indicadores()) == 81


def test_main_com_banco_corrompido(tmp_path):
    banco = tmp_path / "banco.json"
    banco.write_text("{quebrado", encoding="utf-8")
    assert main(["--banco", str(banco)]) == 1


def test_script_seed(tmp_path):
    banco = tmp_path / "banco.json"
    comando = [sys.executable, str(RAIZ / "scripts" / "seed.py"), "--banco", str(banco)]
    primeira = subprocess.run(comando, capture_output=True, text=True, encoding="utf-8")
    assert primeira.returncode == 0 and "calculado   2054   informado   2372" in primeira.stdout
    segunda = subprocess.run(comando, capture_output=True, text=True, encoding="utf-8")
    assert segunda.returncode == 1 and "--forcar" in segunda.stdout
    assert subprocess.run(comando + ["--forcar"], capture_output=True).returncode == 0
