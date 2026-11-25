"""Importação de planilha CSV (RF11, RF12, RN01 – UC04; diagrama de sequência da SRS).

Fluxo em duas etapas:
1. pre_visualizar(): lê o arquivo, valida o layout e cada linha, e devolve
   uma Importacao PENDENTE com linhas válidas e com erro (nada é gravado).
2. confirmar(): o Digitador confirma e as linhas válidas viram lançamentos.

Layout (SRS seção 10): modulo;codigo_indicador;ano;mes;valor
Aceita separador ";" ou "," e vírgula decimal (ex.: 0,2).
"""

from __future__ import annotations

import csv
import io
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Callable

from ..excecoes import DadoPessoalDetectado, ErroSistema, ErroValidacao
from ..models import Importacao, LancamentoMensal, OrigemDado, Permissao, Usuario
from ..persistence import Repositorio
from .auditoria import ServicoAuditoria
from .autenticacao import exigir_permissao
from .lancamentos import ServicoLancamentos

COLUNAS_OBRIGATORIAS = ("modulo", "codigo_indicador", "ano", "mes", "valor")

# RN01: colunas que indicam dado pessoal. Basta o nome da coluna CONTER um
# destes termos (ex.: "nome_paciente", "cpf_mae") para o arquivo ser rejeitado.
TERMOS_PROIBIDOS = (
    "nome", "paciente", "cpf", "rg", "cartao_sus", "cns", "endereco",
    "prontuario", "nascimento", "telefone", "mae", "email",
)


def _normalizar(texto: str) -> str:
    """'Código Indicador' → 'codigo_indicador'."""
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return sem_acento.strip().lower().replace(" ", "_").replace("-", "_")


def _inteiro(texto: str, campo: str) -> int:
    try:
        return int(texto.strip())
    except (ValueError, AttributeError):
        raise ErroValidacao(f"{campo} deve ser um número inteiro (recebido: {texto!r}).") from None


def _numero(texto: str) -> float | int:
    texto = (texto or "").strip().replace(",", ".")
    try:
        numero = float(texto)
    except ValueError:
        raise ErroValidacao(f"valor deve ser numérico (recebido: {texto!r}).") from None
    return int(numero) if numero.is_integer() else numero


class ServicoImportacao:
    def __init__(
        self,
        repositorio: Repositorio,
        lancamentos: ServicoLancamentos,
        auditoria: ServicoAuditoria,
        relogio: Callable[[], datetime] = datetime.now,
    ) -> None:
        self._repo = repositorio
        self._lancamentos = lancamentos
        self._auditoria = auditoria
        self._relogio = relogio

    # ---------------------------------------------------------- leitura
    @staticmethod
    def _ler_csv(conteudo: str) -> tuple[list[str], list[dict[str, str]]]:
        """Devolve (colunas normalizadas, linhas)."""
        if not conteudo.strip():
            raise ErroValidacao("O arquivo está vazio.")
        try:
            dialeto = csv.Sniffer().sniff(conteudo.splitlines()[0], delimiters=";,")
            separador = dialeto.delimiter
        except (csv.Error, IndexError):
            separador = ";"
        leitor = csv.DictReader(io.StringIO(conteudo), delimiter=separador)
        if not leitor.fieldnames:
            raise ErroValidacao("O arquivo está vazio ou sem cabeçalho.")
        colunas = [_normalizar(c) for c in leitor.fieldnames]
        leitor.fieldnames = colunas
        return colunas, list(leitor)

    @staticmethod
    def validar_layout(colunas: list[str]) -> None:
        """Passos 3–4 do diagrama de sequência: colunas OK / colunas proibidas."""
        proibidas = [c for c in colunas if any(t in c.split("_") or c.startswith(t) for t in TERMOS_PROIBIDOS)]
        if proibidas:
            raise DadoPessoalDetectado(
                "Arquivo rejeitado (LGPD): colunas com possível dado pessoal: "
                + ", ".join(proibidas)
                + ". O sistema aceita apenas totais agregados."
            )
        faltando = [c for c in COLUNAS_OBRIGATORIAS if c not in colunas]
        if faltando:
            raise ErroValidacao("Colunas obrigatórias ausentes: " + ", ".join(faltando))

    def _montar_lancamento(self, linha: dict[str, str]) -> LancamentoMensal:
        indicador = self._repo.buscar_indicador(
            (linha.get("codigo_indicador") or "").strip().upper(),
            (linha.get("modulo") or "").strip().upper(),
        )
        return LancamentoMensal(
            indicador,
            _inteiro(linha.get("ano"), "ano"),
            _inteiro(linha.get("mes"), "mes"),
            _numero(linha.get("valor")),
            OrigemDado.IMPORTACAO,
        )

    # ---------------------------------------------------------- etapa 1
    def pre_visualizar(self, usuario: Usuario, conteudo: str, nome_arquivo: str = "planilha.csv") -> Importacao:
        exigir_permissao(usuario, Permissao.IMPORTAR_PLANILHA)
        colunas, linhas = self._ler_csv(conteudo)
        self.validar_layout(colunas)

        importacao = Importacao(nome_arquivo, realizada_por=usuario.login, data_hora=self._relogio())
        hoje = self._relogio().date()
        chaves_no_arquivo: set[tuple] = set()

        for numero, linha in enumerate(linhas, start=2):  # linha 1 = cabeçalho
            try:
                lancamento = self._montar_lancamento(linha)
                lancamento.validar(hoje)
                self._lancamentos.verificar_periodo_aberto(lancamento)
                if lancamento.chave() in chaves_no_arquivo:
                    raise ErroValidacao("linha repetida no arquivo (mesmo indicador, ano e mês).")
                chaves_no_arquivo.add(lancamento.chave())
            except ErroSistema as erro:
                importacao.adicionar_rejeitada(numero, str(erro))
                continue
            importacao.adicionar_valida(
                {
                    "modulo": lancamento.indicador.modulo.sigla,
                    "codigo_indicador": lancamento.indicador.codigo,
                    "ano": lancamento.ano,
                    "mes": lancamento.mes,
                    "valor": lancamento.valor,
                    "substitui": self._lancamentos.existe(lancamento),  # conflito (RN04)
                }
            )
        self._repo.salvar_importacao(importacao)
        return importacao

    def pre_visualizar_arquivo(self, usuario: Usuario, caminho: str | Path) -> Importacao:
        caminho = Path(caminho)
        conteudo = caminho.read_text(encoding="utf-8-sig")
        return self.pre_visualizar(usuario, conteudo, caminho.name)

    # ---------------------------------------------------------- etapa 2
    def confirmar(self, usuario: Usuario, importacao_id: int) -> dict[str, int]:
        """Passos 10–15 do diagrama de sequência. Devolve o resumo da gravação."""
        exigir_permissao(usuario, Permissao.IMPORTAR_PLANILHA)
        importacao = self._repo.obter_importacao(importacao_id)

        # 1º monta e valida TODAS as linhas; só depois grava (tudo ou nada).
        hoje = self._relogio().date()
        lancamentos = []
        for linha in importacao.validas:
            lancamento = self._montar_lancamento({k: str(v) for k, v in linha.items()})
            lancamento.importacao_id = importacao.id
            lancamento.validar(hoje)
            self._lancamentos.verificar_periodo_aberto(lancamento)
            lancamentos.append(lancamento)
        importacao.confirmar()

        resumo = {"inseridos": 0, "substituidos": 0, "rejeitados": importacao.linhas_rejeitadas}
        for lancamento in lancamentos:
            substitui = self._lancamentos.existe(lancamento)
            self._lancamentos.registrar(usuario, lancamento, confirmar_substituicao=True, salvar=False)
            resumo["substituidos" if substitui else "inseridos"] += 1

        self._auditoria.registrar(
            usuario.login, "importar", f"Importacao {importacao.id} ({importacao.nome_arquivo})",
            None, f"{resumo['inseridos']} inseridos, {resumo['substituidos']} substituídos",
        )
        self._repo.salvar()  # gravação única ao final
        return resumo

    def cancelar(self, usuario: Usuario, importacao_id: int) -> None:
        exigir_permissao(usuario, Permissao.IMPORTAR_PLANILHA)
        self._repo.obter_importacao(importacao_id).cancelar()
        self._repo.salvar()
