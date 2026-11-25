"""Menu principal no terminal (substitui a interface web – alteração A05).

A interface NÃO tem regra de negócio: ela só pergunta, chama os serviços
e mostra o resultado. Toda validação acontece nas classes e nos serviços,
e os erros chegam aqui como exceções com mensagem pronta (RF12).

O menu mostra só as opções que o perfil pode usar (RF09). Mesmo assim, os
serviços conferem a permissão de novo, como uma segunda barreira.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Callable

from ..excecoes import ErroAutenticacao, ErroSistema, RegistroDuplicado
from ..models import CicloPNCD, LevantamentoLIRAa, Permissao
from ..services import Periodo, Sessao, Sistema
from ..services.indicadores import NOMES_MESES
from .console import Console


@dataclass
class OpcaoMenu:
    texto: str
    permissao: str | None
    acao: Callable[[], None]


class Aplicacao:
    def __init__(self, sistema: Sistema, console: Console | None = None,
                 pasta_exportacao: str | Path = "exportacoes") -> None:
        self.sistema = sistema
        self.console = console or Console()
        self.pasta_exportacao = Path(pasta_exportacao)
        self.sessao: Sessao | None = None

    # ================================================================ fluxo
    @property
    def usuario(self):
        return self.sessao.usuario if self.sessao else None

    def executar(self) -> None:
        self.console.titulo("Sistema de Indicadores da Vigilância Epidemiológica – Balsas-MA")
        self.console.escrever("Somente dados agregados: nunca informe dados de pacientes (LGPD).")
        try:
            while True:
                if not self.entrar():
                    break
                self.menu_principal()
        except (KeyboardInterrupt, EOFError):
            self.console.escrever("\nEncerrando.")

    def entrar(self) -> bool:
        """UC01. Devolve False se o usuário quiser fechar o programa."""
        while True:
            self.console.escrever()
            login = self.console.perguntar("Login (Enter para sair)", padrao="")
            if not login:
                return False
            try:
                self.sessao = self.sistema.autenticacao.entrar(login, self.console.senha())
            except ErroAutenticacao as erro:
                self.console.erro(str(erro))
                continue
            u = self.sessao.usuario
            self.console.sucesso(f"Bem-vindo(a), {u.nome} – perfil {u.perfil.nome}.")
            return True

    def opcoes(self) -> list[OpcaoMenu]:
        todas = [
            OpcaoMenu("Painel epidemiológico", Permissao.VER_PAINEL, self.painel),
            OpcaoMenu("Comparar períodos", Permissao.VER_PAINEL, self.comparar),
            OpcaoMenu("Consultar indicadores (com filtros)", Permissao.VER_PAINEL, self.consultar),
            OpcaoMenu("Lançar total mensal (SINAN, LACEN, SIM/SINASC)", Permissao.LANCAR_DADOS, self.lancar_total),
            OpcaoMenu("Registrar ciclo do PNCD", Permissao.LANCAR_DADOS, self.registrar_ciclo),
            OpcaoMenu("Registrar LIRAa", Permissao.LANCAR_DADOS, self.registrar_liraa),
            OpcaoMenu("Importar planilha CSV", Permissao.IMPORTAR_PLANILHA, self.importar),
            OpcaoMenu("Homologar / reabrir quadrimestre", Permissao.HOMOLOGAR_RELATORIO, self.homologar),
            OpcaoMenu("Exportar relatório (CSV ou TXT)", Permissao.EXPORTAR_RELATORIO, self.exportar),
            OpcaoMenu("Gerenciar usuários", Permissao.GERENCIAR_USUARIOS, self.gerenciar_usuarios),
            OpcaoMenu("Ver auditoria", Permissao.GERENCIAR_USUARIOS, self.ver_auditoria),
        ]
        return [o for o in todas if o.permissao is None or self.usuario.tem_permissao(o.permissao)]

    def menu_principal(self) -> None:
        while self.sessao:
            opcoes = self.opcoes()
            self.console.titulo(f"Menu – {self.usuario.nome} ({self.usuario.perfil.nome})")
            for n, opcao in enumerate(opcoes, start=1):
                self.console.escrever(f"  {n:>2}. {opcao.texto}")
            self.console.escrever("   0. Sair (trocar de usuário)")
            escolha = self.console.ler_inteiro("Opção", 0, len(opcoes))
            if escolha == 0:
                self.sistema.autenticacao.sair(self.sessao)
                self.sessao = None
                return
            self.executar_opcao(opcoes[escolha - 1])

    def executar_opcao(self, opcao: OpcaoMenu) -> None:
        try:
            self.sistema.autenticacao.validar_sessao(self.sessao)  # RNF05: expiração
        except ErroAutenticacao as erro:
            self.console.erro(str(erro))
            self.sessao = None
            return
        try:
            opcao.acao()
        except ErroSistema as erro:
            self.console.erro(str(erro))

    # ============================================================ auxiliares
    def ler_quadrimestre(self, padrao: Periodo | None = None) -> Periodo:
        padrao = padrao or self.sistema.indicadores.ultimo_quadrimestre_com_dados() \
            or Periodo.quadrimestre(date.today().year, 1)
        ano = self.console.ler_inteiro("Ano", 2000, 2100, padrao.ano)
        quad = self.console.ler_inteiro("Quadrimestre (1, 2 ou 3)", 1, 3, padrao.numero)
        return Periodo.quadrimestre(ano, quad)

    def ler_periodo(self) -> Periodo:
        tipos = ["Mês", "Quadrimestre", "Ano"]
        tipo = self.console.escolher("Tipo de período", tipos)
        ano = self.console.ler_inteiro("Ano", 2000, 2100)
        if tipo == 0:
            return Periodo.mes(ano, self.console.ler_inteiro("Mês (1–12)", 1, 12))
        if tipo == 1:
            return Periodo.quadrimestre(ano, self.console.ler_inteiro("Quadrimestre (1–3)", 1, 3))
        return Periodo.anual(ano)

    def ler_filtros(self) -> dict:
        """RF07: filtro por sistema de origem e grupo epidemiológico."""
        modulos = self.sistema.repositorio.listar_modulos()
        i = self.console.escolher("Sistema de origem", [str(m) for m in modulos], permitir_vazio=True)
        modulo = modulos[i].sigla if i is not None else None
        grupos = self.sistema.indicadores.grupos(modulo)
        g = self.console.escolher("Grupo epidemiológico", grupos, permitir_vazio=True) if grupos else None
        return {"modulo": modulo, "grupo": grupos[g] if g is not None else None}

    def escolher_indicador(self):
        modulos = [m for m in self.sistema.repositorio.listar_modulos() if len(m) > 0]
        modulo = modulos[self.console.escolher("Módulo", [str(m) for m in modulos])]
        busca = self.console.perguntar("Parte do nome ou código (Enter lista todos)", padrao="").lower()
        candidatos = [i for i in modulo.indicadores
                      if i.ativo and (busca in i.nome.lower() or busca in i.codigo.lower())]
        if not candidatos:
            raise ErroSistema("Nenhum indicador encontrado com esse termo.")
        return candidatos[self.console.escolher("Indicador", [f"{i.nome} [{i.codigo}]" for i in candidatos])]

    @staticmethod
    def _num(valor) -> str:
        if isinstance(valor, float):
            return f"{valor:.2f}".replace(".", ",")
        return f"{valor:,}".replace(",", ".") if isinstance(valor, int) else str(valor)

    # ============================================================ painel
    def painel(self) -> None:
        """RF05 / UC06."""
        ind = self.sistema.indicadores
        self.console.escrever("Período do painel (Enter = último quadrimestre com dados):")
        resumo = ind.painel(self.usuario, self.ler_quadrimestre())
        self.console.titulo(f"Painel epidemiológico – {resumo.periodo}")
        self.console.tabela(
            ["Indicador", "Atual", "Ano anterior", "Variação"],
            [[c.titulo, self._num(c.valor),
              "—" if c.valor_ano_anterior in (None, 0) else self._num(c.valor_ano_anterior),
              ind.formatar_variacao(c.variacao)] for c in resumo.cartoes],
        )
        self.console.escrever("\nPrincipais agravos notificados (SINAN):")
        self.console.grafico_barras(resumo.principais_agravos)
        self.console.escrever("\nEvolução mensal das notificações (SINAN):")
        self.console.grafico_barras(list(resumo.serie_mensal.items()))

    def comparar(self) -> None:
        """RF06 / UC07."""
        self.console.escrever("Período atual:")
        atual = self.ler_periodo()
        if self.console.confirmar(f"Comparar com o mesmo período do ano anterior ({atual.mesmo_periodo_ano_anterior()})?"):
            base = atual.mesmo_periodo_ano_anterior()
        else:
            self.console.escrever("Período de comparação:")
            base = self.ler_periodo()
        filtros = self.ler_filtros()
        linhas = self.sistema.indicadores.comparar(self.usuario, atual, base, **filtros)
        self.console.titulo(f"Comparativo: {atual} × {base}")
        fmt = self.sistema.indicadores.formatar_variacao
        self.console.tabela(
            ["Indicador", str(atual), str(base), "Diferença", "Variação"],
            [[l.nome, self._num(l.valor_atual), self._num(l.valor_base),
              f"{l.diferenca:+}", fmt(l.variacao)] for l in linhas],
        )

    def consultar(self) -> None:
        """RF07 / UC08: valores mensais e total calculado de cada indicador."""
        periodo = self.ler_quadrimestre()
        filtros = self.ler_filtros()
        ind = self.sistema.indicadores
        linhas, total_geral = [], 0
        for indicador in ind.filtrar_indicadores(**filtros):
            valores = ind.valores_mensais(indicador, periodo)
            total = sum(valores.values())
            if total:
                linhas.append([indicador.nome, *map(self._num, valores.values()), self._num(total)])
                total_geral += total
        self.console.titulo(f"Indicadores – {periodo}")
        self.console.tabela(["Indicador", *[NOMES_MESES[m - 1] for m in periodo.meses], "Total"], linhas)
        # O total só faz sentido somando coisas da mesma natureza
        somavel = filtros["modulo"] == "SINAN" or filtros["grupo"] == "Exames LACEN"
        if linhas and somavel:
            self.console.escrever(f"\nTotal calculado pelo sistema (RN06): {self._num(total_geral)}")

    # ======================================================== lançamentos
    def _registrar_com_confirmacao(self, registro) -> bool:
        """RN04: se já existir, pergunta antes de substituir. Devolve True se gravou."""
        try:
            self.sistema.lancamentos.registrar(self.usuario, registro)
        except RegistroDuplicado as aviso:
            self.console.erro(str(aviso))
            if not self.console.confirmar("Substituir o valor existente?"):
                self.console.escrever("Nada foi alterado.")
                return False
            self.sistema.lancamentos.registrar(self.usuario, registro, confirmar_substituicao=True)
        self.console.sucesso(f"Registrado: {registro}")
        return True

    def lancar_total(self) -> None:
        """RF01, RF02, RF04 / UC03."""
        from ..models import LancamentoMensal

        indicador = self.escolher_indicador()
        hoje = date.today()
        ano = self.console.ler_inteiro("Ano", 2000, 2100, hoje.year)
        mes = self.console.ler_inteiro("Mês (1–12)", 1, 12)
        valor = self.console.ler_numero(f"Total de {indicador.nome}")
        if not self._registrar_com_confirmacao(LancamentoMensal(indicador, ano, mes, valor)):
            return
        periodo = Periodo.quadrimestre(ano, (mes - 1) // 4 + 1)
        total = self.sistema.indicadores.total([indicador], periodo)
        self.console.escrever(f"Total de {indicador.nome} no {periodo}: {self._num(total)} (recalculado)")

    def registrar_ciclo(self) -> None:
        """RF03 / RN08."""
        endemias = self.sistema.repositorio.obter_modulo("ENDEMIAS")
        ano = self.console.ler_inteiro("Ano", 2000, 2100, date.today().year)
        numero = self.console.ler_inteiro("Número do ciclo (1–6)", 1, 6)
        mes_inicial = self.console.ler_inteiro("Mês inicial do ciclo (1–11)", 1, 11)
        programados = self.console.ler_inteiro("Imóveis programados", 1)
        trabalhados = self.console.ler_inteiro("Imóveis trabalhados", 0)
        ciclo = CicloPNCD(endemias, ano, numero, mes_inicial, programados, trabalhados)
        self._registrar_com_confirmacao(ciclo)

    def registrar_liraa(self) -> None:
        """RF03 / RN09."""
        endemias = self.sistema.repositorio.obter_modulo("ENDEMIAS")
        inicio = self._ler_data("Data inicial (dd/mm/aaaa)")
        fim = self._ler_data("Data final (dd/mm/aaaa)")
        iip = self.console.ler_numero("Índice de Infestação Predial (IIP %)")
        ib = self.console.ler_numero("Índice de Breteau (IB)")
        pontos = self.console.ler_inteiro("Pontos estratégicos tratados", 0, padrao=0)
        levantamento = LevantamentoLIRAa(endemias, inicio, fim, iip, ib, pontos)
        if self._registrar_com_confirmacao(levantamento):
            self.console.escrever(f"Classificação de risco (RN09): {levantamento.classificar_risco()}")

    def _ler_data(self, texto: str) -> date:
        while True:
            try:
                return datetime.strptime(self.console.perguntar(texto), "%d/%m/%Y").date()
            except ValueError:
                self.console.erro("Data inválida. Use o formato dd/mm/aaaa.")

    # ========================================================= importação
    def importar(self) -> None:
        """RF11 / UC04 – fluxo do diagrama de sequência."""
        caminho = Path(self.console.perguntar("Caminho do arquivo CSV", padrao="data/exemplo_importacao.csv"))
        if not caminho.exists():
            raise ErroSistema(f"Arquivo não encontrado: {caminho}")
        imp = self.sistema.importacao.pre_visualizar_arquivo(self.usuario, caminho)
        self.console.titulo(f"Prévia da importação – {imp.nome_arquivo} ({len(imp)} linhas)")
        conflitos = sum(1 for l in imp.validas if l["substitui"])
        self.console.escrever(f"Linhas válidas: {imp.linhas_validas}  (substituem valores existentes: {conflitos})")
        self.console.escrever(f"Linhas com erro: {imp.linhas_rejeitadas}")
        for numero, mensagem in imp.erros:
            self.console.escrever(f"  linha {numero}: {mensagem}")
        if not imp.linhas_validas:
            self.sistema.importacao.cancelar(self.usuario, imp.id)
            self.console.erro("Nenhuma linha válida. Importação cancelada.")
            return
        if not self.console.confirmar("Confirmar a gravação das linhas válidas?"):
            self.sistema.importacao.cancelar(self.usuario, imp.id)
            self.console.escrever("Importação cancelada. Nada foi gravado.")
            return
        resumo = self.sistema.importacao.confirmar(self.usuario, imp.id)
        self.console.sucesso(
            f"{resumo['inseridos']} inseridos, {resumo['substituidos']} substituídos, "
            f"{resumo['rejeitados']} rejeitados."
        )

    # ========================================================= relatórios
    def homologar(self) -> None:
        """RF14 / UC10 / RN11."""
        periodo = self.ler_quadrimestre()
        relatorio = self.sistema.relatorios.obter(periodo.ano, periodo.numero)
        self.console.escrever(f"Situação atual: {relatorio}")
        if relatorio.esta_bloqueado:
            if self.console.confirmar("O período está homologado. Deseja reabrir?"):
                justificativa = self.console.perguntar("Justificativa da reabertura")
                self.sistema.relatorios.reabrir(self.usuario, periodo.ano, periodo.numero, justificativa)
                self.console.sucesso("Período reaberto para correções.")
        elif self.console.confirmar(f"Homologar o {periodo}? Os dados do período ficarão bloqueados"):
            self.sistema.relatorios.homologar(self.usuario, periodo.ano, periodo.numero)
            self.console.sucesso(f"{periodo} homologado.")

    def exportar(self) -> None:
        """RF08 / UC09."""
        periodo = self.ler_quadrimestre()
        formato = ["csv", "txt"][self.console.escolher("Formato", ["CSV (abre no Excel)", "TXT (para imprimir)"])]
        caminho = self.sistema.relatorios.exportar(
            self.usuario, periodo.ano, periodo.numero, formato, self.pasta_exportacao
        )
        self.console.sucesso(f"Relatório gerado em {caminho}")

    # =========================================================== usuários
    def gerenciar_usuarios(self) -> None:
        """RF10 / UC02."""
        servico = self.sistema.usuarios
        usuarios = servico.listar(self.usuario)
        self.console.titulo("Usuários")
        self.console.tabela(
            ["Login", "Nome", "Perfil", "Situação"],
            [[u.login, u.nome, u.perfil.nome, "ativo" if u.ativo else "inativo"] for u in usuarios],
        )
        acoes = ["Cadastrar usuário", "Inativar usuário", "Reativar usuário",
                 "Redefinir senha", "Alterar perfil", "Voltar"]
        acao = self.console.escolher("Ação", acoes)
        if acao == 5:
            return
        perfis = [p.nome for p in self.sistema.repositorio.listar_perfis()]
        if acao == 0:
            nome = self.console.perguntar("Nome")
            login = self.console.perguntar("Login")
            senha = self.console.senha("Senha (mínimo 8 caracteres)")
            perfil = perfis[self.console.escolher("Perfil", perfis)]
            self.console.sucesso(f"Cadastrado: {servico.cadastrar(self.usuario, nome, login, senha, perfil)}")
            return
        login = self.console.perguntar("Login do usuário")
        if acao == 1:
            self.console.sucesso(f"Inativado: {servico.inativar(self.usuario, login)}")
        elif acao == 2:
            self.console.sucesso(f"Reativado: {servico.ativar(self.usuario, login)}")
        elif acao == 3:
            servico.redefinir_senha(self.usuario, login, self.console.senha("Nova senha"))
            self.console.sucesso("Senha redefinida.")
        elif acao == 4:
            perfil = perfis[self.console.escolher("Novo perfil", perfis)]
            self.console.sucesso(f"Alterado: {servico.alterar_perfil(self.usuario, login, perfil)}")

    def ver_auditoria(self) -> None:
        """RNF10: últimas operações registradas."""
        logs = self.sistema.auditoria.listar()[-20:]
        self.console.titulo("Auditoria – últimas 20 operações")
        for log in logs:
            self.console.escrever(str(log))
