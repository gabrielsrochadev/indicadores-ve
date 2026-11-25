"""Enumerações usadas no Diagrama de Classes (alteração A03).

Os valores são textos para facilitar a gravação em JSON.
"""

from enum import Enum


class TipoValor(str, Enum):
    """Tipo de número que um indicador aceita (RN05 / A08)."""

    INTEIRO = "inteiro"
    DECIMAL = "decimal"


class Periodicidade(str, Enum):
    """Frequência com que o indicador é apurado."""

    MENSAL = "mensal"
    BIMESTRAL = "bimestral"
    QUADRIMESTRAL = "quadrimestral"


class OrigemDado(str, Enum):
    """Como o lançamento entrou no sistema (RF01–RF04 ou RF11)."""

    DIGITACAO = "digitacao"
    IMPORTACAO = "importacao"


class StatusRelatorio(str, Enum):
    """Situação do relatório quadrimestral (RF14, RN11)."""

    RASCUNHO = "rascunho"
    HOMOLOGADO = "homologado"
    REABERTO = "reaberto"


class StatusImportacao(str, Enum):
    """Situação de uma importação de planilha (RF11)."""

    PENDENTE = "pendente"
    CONFIRMADA = "confirmada"
    CANCELADA = "cancelada"
