"""Exportação de relatórios (RF08, alteração A06).

Exportador (classe abstrata)
├── ExportadorCSV  → planilha que abre no Excel (separador ";", UTF-8 com BOM)
└── ExportadorTXT  → relatório de texto pronto para imprimir

Os dois recebem o MESMO conteúdo (ConteudoRelatorio) e cada um sobrescreve
gerar() do seu jeito: polimorfismo.
"""

from __future__ import annotations

import csv
import io
from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class TabelaRelatorio:
    titulo: str
    colunas: list[str]
    linhas: list[list[object]] = field(default_factory=list)


@dataclass
class ConteudoRelatorio:
    cabecalho: list[str]
    tabelas: list[TabelaRelatorio] = field(default_factory=list)


def _formatar(valor: object) -> str:
    """Números no padrão brasileiro: 98.57 → 98,57."""
    if isinstance(valor, float):
        return f"{valor:.2f}".replace(".", ",")
    return str(valor)


class Exportador(ABC):
    """Contrato de todo formato de exportação."""

    extensao: str = ""
    codificacao: str = "utf-8"

    @abstractmethod
    def gerar(self, conteudo: ConteudoRelatorio) -> str:
        """Transforma o conteúdo do relatório em texto do formato."""

    def __str__(self) -> str:
        return self.extensao.upper()


class ExportadorCSV(Exportador):
    extensao = "csv"
    codificacao = "utf-8-sig"  # BOM: o Excel reconhece os acentos

    def gerar(self, conteudo: ConteudoRelatorio) -> str:
        saida = io.StringIO()
        escritor = csv.writer(saida, delimiter=";", lineterminator="\n")
        for linha in conteudo.cabecalho:
            escritor.writerow([linha])
        for tabela in conteudo.tabelas:
            escritor.writerow([])
            escritor.writerow([tabela.titulo])
            escritor.writerow(tabela.colunas)
            for linha in tabela.linhas:
                escritor.writerow([_formatar(v) for v in linha])
        return saida.getvalue()


class ExportadorTXT(Exportador):
    extensao = "txt"

    def gerar(self, conteudo: ConteudoRelatorio) -> str:
        largura = 78
        partes = ["=" * largura]
        partes += [linha.center(largura).rstrip() for linha in conteudo.cabecalho]
        partes.append("=" * largura)
        for tabela in conteudo.tabelas:
            partes += ["", tabela.titulo, "-" * largura]
            textos = [tabela.colunas] + [[_formatar(v) for v in l] for l in tabela.linhas]
            larguras = [max(len(str(l[i])) for l in textos) for i in range(len(tabela.colunas))]
            for numero, linha in enumerate(textos):
                celulas = [
                    str(c).ljust(larguras[i]) if i == 0 else str(c).rjust(larguras[i])
                    for i, c in enumerate(linha)
                ]
                partes.append("  ".join(celulas))
                if numero == 0:
                    partes.append("-" * largura)
        return "\n".join(partes) + "\n"


EXPORTADORES: dict[str, Exportador] = {"csv": ExportadorCSV(), "txt": ExportadorTXT()}
