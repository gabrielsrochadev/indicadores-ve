"""Relatório quadrimestral: homologação, reabertura e exportação
(RF08, RF14 – UC09, UC10; RN11)."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Callable

from ..excecoes import ErroValidacao
from ..models import Permissao, RelatorioQuadrimestral, Usuario
from ..persistence import Repositorio
from .auditoria import ServicoAuditoria
from .autenticacao import exigir_permissao
from .exportadores import EXPORTADORES, ConteudoRelatorio, TabelaRelatorio
from .indicadores import NOMES_MESES, Periodo, ServicoIndicadores

ORGAO = "Secretaria Municipal de Saúde de Balsas-MA"
SETOR = "Coordenação de Vigilância Epidemiológica – Rua São Pedro, S/N – Nazaré"


class ServicoRelatorios:
    def __init__(
        self,
        repositorio: Repositorio,
        indicadores: ServicoIndicadores,
        auditoria: ServicoAuditoria,
        relogio: Callable[[], datetime] = datetime.now,
    ) -> None:
        self._repo = repositorio
        self._indicadores = indicadores
        self._auditoria = auditoria
        self._relogio = relogio

    def obter(self, ano: int, quadrimestre: int) -> RelatorioQuadrimestral:
        """Relatório do período; cria um rascunho se ainda não existir."""
        relatorio = self._repo.obter_relatorio(ano, quadrimestre)
        if relatorio is None:
            relatorio = self._repo.salvar_relatorio(RelatorioQuadrimestral(ano, quadrimestre))
        return relatorio

    # ------------------------------------------------------------ RF14
    def homologar(self, usuario: Usuario, ano: int, quadrimestre: int) -> RelatorioQuadrimestral:
        exigir_permissao(usuario, Permissao.HOMOLOGAR_RELATORIO)
        relatorio = self.obter(ano, quadrimestre)
        if not self._repo.lancamentos() or not any(
            relatorio.contem(l.ano, l.mes) for l in self._repo.lancamentos()
        ):
            raise ErroValidacao("Não há lançamentos neste quadrimestre para homologar.")
        anterior = relatorio.status.value
        relatorio.homologar(usuario, self._relogio())
        self._auditoria.registrar(usuario.login, "homologar", str(relatorio), anterior, relatorio.status.value)
        self._repo.salvar()
        return relatorio

    def reabrir(self, usuario: Usuario, ano: int, quadrimestre: int, justificativa: str) -> RelatorioQuadrimestral:
        exigir_permissao(usuario, Permissao.HOMOLOGAR_RELATORIO)
        relatorio = self.obter(ano, quadrimestre)
        relatorio.reabrir(usuario, justificativa)
        self._auditoria.registrar(usuario.login, "reabrir", str(relatorio), "homologado", justificativa)
        self._repo.salvar()
        return relatorio

    # ------------------------------------------------------------ RF08
    def montar_conteudo(self, usuario: Usuario, ano: int, quadrimestre: int) -> ConteudoRelatorio:
        relatorio = self.obter(ano, quadrimestre)
        periodo = Periodo.quadrimestre(ano, quadrimestre)
        meses = [NOMES_MESES[m - 1] for m in periodo.meses]

        if relatorio.esta_bloqueado:
            situacao = (
                f"Situação: HOMOLOGADO em {relatorio.homologado_em:%d/%m/%Y %H:%M} "
                f"por {relatorio.homologado_por} (versão {relatorio.versao})"
            )
        else:
            situacao = f"Situação: {relatorio.status.value.upper()} – não homologado (versão {relatorio.versao})"

        conteudo = ConteudoRelatorio(
            cabecalho=[
                ORGAO,
                SETOR,
                f"Relatório do {quadrimestre}º quadrimestre de {ano} ({meses[0]}–{meses[-1]})",
                f"Emitido em {self._relogio():%d/%m/%Y %H:%M} por {usuario.login}",
                situacao,
            ]
        )

        # Uma tabela por módulo com lançamentos mensais (totais calculados – RN06)
        for modulo in self._repo.listar_modulos():
            tabela = TabelaRelatorio(f"{modulo.sigla} – {modulo.nome}", ["Indicador", *meses, "Total"])
            total_geral = 0
            for indicador in modulo.indicadores:
                valores = self._indicadores.valores_mensais(indicador, periodo)
                total = sum(valores.values())
                if total == 0:
                    continue
                tabela.linhas.append([indicador.nome, *valores.values(), total])
                total_geral += total
            if tabela.linhas:
                if modulo.sigla in ("SINAN", "LACEN"):
                    tabela.linhas.append(["TOTAL (calculado)", *[""] * len(meses), total_geral])
                conteudo.tabelas.append(tabela)

        ciclos = [c for c in self._repo.ciclos_pncd() if periodo.contem(c.ano, c.mes_referencia)]
        if ciclos:
            tabela = TabelaRelatorio("Cobertura por ciclo – PNCD", ["Ciclo", "Meses", "Programados", "Trabalhados", "Cobertura %"])
            for c in ciclos:
                tabela.linhas.append([f"{c.numero}/{c.ano}", f"{NOMES_MESES[c.mes_inicial-1]}/{NOMES_MESES[c.mes_final-1]}",
                                      c.imoveis_programados, c.imoveis_trabalhados, c.cobertura()])
            conteudo.tabelas.append(tabela)

        levantamentos = [l for l in self._repo.levantamentos_liraa() if periodo.contem(l.ano, l.mes_referencia)]
        if levantamentos:
            tabela = TabelaRelatorio("LIRAa", ["Período", "IIP", "IB", "Pontos estratégicos", "Classificação"])
            for l in levantamentos:
                tabela.linhas.append([f"{l.data_inicio:%d/%m}–{l.data_fim:%d/%m/%Y}", l.indice_predial,
                                      l.indice_breteau, l.pontos_estrategicos, l.classificar_risco()])
            conteudo.tabelas.append(tabela)
        return conteudo

    def exportar(
        self,
        usuario: Usuario,
        ano: int,
        quadrimestre: int,
        formato: str = "csv",
        pasta: str | Path = "exportacoes",
    ) -> Path:
        exigir_permissao(usuario, Permissao.EXPORTAR_RELATORIO)
        exportador = EXPORTADORES.get(formato.lower())
        if exportador is None:
            raise ErroValidacao(f"Formato {formato!r} não suportado. Use: {', '.join(EXPORTADORES)}.")
        conteudo = self.montar_conteudo(usuario, ano, quadrimestre)
        relatorio = self.obter(ano, quadrimestre)

        pasta = Path(pasta)
        pasta.mkdir(parents=True, exist_ok=True)
        caminho = pasta / f"relatorio_{ano}_Q{quadrimestre}_v{relatorio.versao}.{exportador.extensao}"
        caminho.write_text(exportador.gerar(conteudo), encoding=exportador.codificacao)

        self._auditoria.registrar(usuario.login, "exportar", str(relatorio), None, caminho.name)
        self._repo.salvar()
        return caminho
