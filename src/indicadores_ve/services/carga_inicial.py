"""Carga inicial a partir de data/dados_iniciais.json.

Os dados vêm do relatório oficial do 2º quadrimestre de 2026. Cada valor
passa pelas mesmas validações do sistema (os setters das classes e o
validar() de cada registro), então a carga também testa as regras.

Ao final, compara os totais CALCULADOS pelo sistema com os totais que o
relatório INFORMOU, para evidenciar a RN06 (totais nunca são digitados).
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from ..models import CicloPNCD, LancamentoMensal, LevantamentoLIRAa, Modulo, OrigemDado, Usuario
from ..persistence import Repositorio
from .indicadores import Periodo, ServicoIndicadores
from .usuarios import DIGITADOR, criar_perfis_padrao


def carregar_dados_iniciais(
    repositorio: Repositorio,
    caminho: str | Path = "data/dados_iniciais.json",
    hoje: date | None = None,
) -> dict:
    """Recria o banco a partir do arquivo de dados iniciais. Devolve um resumo."""
    hoje = hoje or date.today()
    dados = json.loads(Path(caminho).read_text(encoding="utf-8"))
    repositorio.limpar()

    for perfil in criar_perfis_padrao().values():
        repositorio.adicionar_perfil(perfil)
    for u in dados["usuarios"]:
        repositorio.adicionar_usuario(
            Usuario(u["nome"], u["login"], repositorio.obter_perfil(u["perfil"]), senha=u["senha"])
        )
    autor = next((u for u in repositorio.listar_usuarios() if u.perfil.nome == DIGITADOR), None)

    for m in dados["modulos"]:
        modulo = repositorio.adicionar_modulo(Modulo(m["sigla"], m["nome"]))
        for i in m["indicadores"]:
            modulo.adicionar_indicador(
                i["codigo"], i["nome"], i["grupo"],
                i.get("tipo_valor", "inteiro"), i.get("periodicidade", "mensal"),
                id=repositorio.proximo_id("indicadores"),
            )

    for item in dados["lancamentos"]:
        indicador = repositorio.obter_modulo(item["modulo"]).obter_indicador(item["codigo"])
        for mes, valor in item["meses"].items():
            lancamento = LancamentoMensal(
                indicador, item["ano"], int(mes), valor, OrigemDado.DIGITACAO, registrado_por=autor
            )
            lancamento.validar(hoje)
            repositorio.salvar_registro(lancamento)

    endemias = repositorio.obter_modulo("ENDEMIAS")
    for c in dados.get("ciclos_pncd", []):
        ciclo = CicloPNCD(
            endemias, c["ano"], c["numero"], c["mes_inicial"],
            c["imoveis_programados"], c["imoveis_trabalhados"], registrado_por=autor,
        )
        ciclo.validar(hoje)
        repositorio.salvar_registro(ciclo)
    for l in dados.get("levantamentos_liraa", []):
        levantamento = LevantamentoLIRAa(
            endemias, date.fromisoformat(l["data_inicio"]), date.fromisoformat(l["data_fim"]),
            l["indice_predial"], l["indice_breteau"], l.get("pontos_estrategicos", 0),
            registrado_por=autor,
        )
        levantamento.validar(hoje)
        repositorio.salvar_registro(levantamento)

    from .auditoria import ServicoAuditoria  # import local: só usado aqui

    ServicoAuditoria(repositorio).registrar("sistema", "carga_inicial", Path(caminho).name)
    repositorio.salvar()
    return conferir_totais(repositorio, dados.get("totais_informados_no_relatorio", {}))


def conferir_totais(repositorio: Repositorio, informados: dict) -> dict:
    """RN06 na prática: total calculado × total informado no relatório."""
    calc = ServicoIndicadores(repositorio)
    q2 = Periodo.quadrimestre(2026, 2)
    calculados = {
        "SINAN_2026_Q2": calc.total(calc.filtrar_indicadores(modulo="SINAN"), q2),
        "LACEN_2026_Q2": calc.total(calc.filtrar_indicadores(modulo="LACEN", grupo="Exames LACEN"), q2),
        "LAB_PACIENTES_2026_Q2": calc.total_indicador("LAB_PACIENTES", q2),
    }
    return {
        "usuarios": len(repositorio.listar_usuarios()),
        "indicadores": len(repositorio.listar_indicadores()),
        "registros": len(repositorio.listar_registros()),
        "conferencia": {
            chave: {"calculado": calculados[chave], "informado": informados.get(chave)}
            for chave in calculados
        },
    }
