"""Conversão objeto ⇄ dicionário (formato gravado no JSON).

Regras do formato:
- datas e horas em texto ISO (ex.: "2026-11-24T10:00:00");
- enums gravados pelo seu valor (ex.: "inteiro");
- associações gravadas por identificador (login do usuário, código do
  indicador), e reconstruídas como objetos na leitura;
- registros epidemiológicos levam o campo "tipo" com o nome da subclasse,
  para que a leitura saiba qual classe criar (herança).
- a senha nunca é gravada; só o hash (RNF05).
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Callable

from ..excecoes import ErroValidacao
from ..models import (
    CicloPNCD,
    Importacao,
    LancamentoMensal,
    LevantamentoLIRAa,
    LogAuditoria,
    Modulo,
    Perfil,
    Permissao,
    RegistroEpidemiologico,
    RelatorioQuadrimestral,
    Usuario,
)


def _data_hora(texto: str | None) -> datetime | None:
    return datetime.fromisoformat(texto) if texto else None


def _iso(valor: date | datetime | None) -> str | None:
    return valor.isoformat() if valor else None


# ------------------------------------------------------------------ perfis
def perfil_para_dict(perfil: Perfil) -> dict:
    return {
        "id": perfil.id,
        "nome": perfil.nome,
        "descricao": perfil.descricao,
        "permissoes": sorted(
            ({"codigo": p.codigo, "descricao": p.descricao} for p in perfil.permissoes),
            key=lambda p: p["codigo"],
        ),
    }


def perfil_de_dict(dados: dict, permissoes: dict[str, Permissao]) -> Perfil:
    """'permissoes' é compartilhado entre perfis: preserva a agregação."""
    lista = []
    for p in dados["permissoes"]:
        if p["codigo"] not in permissoes:
            permissoes[p["codigo"]] = Permissao(p["codigo"], p.get("descricao", ""))
        lista.append(permissoes[p["codigo"]])
    return Perfil(dados["nome"], dados.get("descricao", ""), lista, id=dados.get("id"))


# ---------------------------------------------------------------- usuários
def usuario_para_dict(usuario: Usuario) -> dict:
    return {
        "id": usuario.id,
        "nome": usuario.nome,
        "login": usuario.login,
        "perfil": usuario.perfil.nome,
        "senha_hash": usuario.senha_hash,
        "ativo": usuario.ativo,
        "ultimo_acesso": _iso(usuario.ultimo_acesso),
    }


def usuario_de_dict(dados: dict, obter_perfil: Callable[[str], Perfil]) -> Usuario:
    return Usuario(
        nome=dados["nome"],
        login=dados["login"],
        perfil=obter_perfil(dados["perfil"]),
        senha_hash=dados["senha_hash"],
        ativo=dados.get("ativo", True),
        ultimo_acesso=_data_hora(dados.get("ultimo_acesso")),
        id=dados.get("id"),
    )


# ---------------------------------------------------- módulos e indicadores
def modulo_para_dict(modulo: Modulo) -> dict:
    return {
        "id": modulo.id,
        "sigla": modulo.sigla,
        "nome": modulo.nome,
        # composição: os indicadores são gravados DENTRO do módulo
        "indicadores": [
            {
                "id": i.id,
                "codigo": i.codigo,
                "nome": i.nome,
                "grupo": i.grupo,
                "tipo_valor": i.tipo_valor.value,
                "periodicidade": i.periodicidade.value,
                "ativo": i.ativo,
            }
            for i in modulo.indicadores
        ],
    }


def modulo_de_dict(dados: dict) -> Modulo:
    modulo = Modulo(dados["sigla"], dados["nome"], id=dados.get("id"))
    for i in dados.get("indicadores", []):
        modulo.adicionar_indicador(
            i["codigo"], i["nome"], i["grupo"],
            i.get("tipo_valor", "inteiro"), i.get("periodicidade", "mensal"),
            i.get("ativo", True), i.get("id"),
        )
    return modulo


# ------------------------------------------------- registros (herança)
def registro_para_dict(registro: RegistroEpidemiologico) -> dict:
    dados = {
        "tipo": type(registro).__name__,
        "id": registro.id,
        "registrado_por": registro.registrado_por.login if registro.registrado_por else None,
        "criado_em": _iso(registro.criado_em),
    }
    if isinstance(registro, LancamentoMensal):
        dados.update(
            modulo=registro.indicador.modulo.sigla,
            codigo_indicador=registro.indicador.codigo,
            ano=registro.ano,
            mes=registro.mes,
            valor=registro.valor,
            origem=registro.origem.value,
            importacao_id=registro.importacao_id,
        )
    elif isinstance(registro, CicloPNCD):
        dados.update(
            modulo=registro.modulo.sigla,
            ano=registro.ano,
            numero=registro.numero,
            mes_inicial=registro.mes_inicial,
            imoveis_programados=registro.imoveis_programados,
            imoveis_trabalhados=registro.imoveis_trabalhados,
        )
    elif isinstance(registro, LevantamentoLIRAa):
        dados.update(
            modulo=registro.modulo.sigla,
            data_inicio=_iso(registro.data_inicio),
            data_fim=_iso(registro.data_fim),
            indice_predial=registro.indice_predial,
            indice_breteau=registro.indice_breteau,
            pontos_estrategicos=registro.pontos_estrategicos,
        )
    else:
        raise ErroValidacao(f"Tipo de registro desconhecido: {type(registro).__name__}")
    return dados


def registro_de_dict(
    dados: dict,
    obter_modulo: Callable[[str], Modulo],
    obter_usuario: Callable[[str], Usuario | None],
) -> RegistroEpidemiologico:
    comum = {
        "registrado_por": obter_usuario(dados.get("registrado_por")),
        "id": dados.get("id"),
        "criado_em": _data_hora(dados.get("criado_em")),
    }
    modulo = obter_modulo(dados["modulo"])
    tipo = dados["tipo"]
    if tipo == "LancamentoMensal":
        return LancamentoMensal(
            modulo.obter_indicador(dados["codigo_indicador"]),
            dados["ano"], dados["mes"], dados["valor"], dados.get("origem", "digitacao"),
            importacao_id=dados.get("importacao_id"), **comum,
        )
    if tipo == "CicloPNCD":
        return CicloPNCD(
            modulo, dados["ano"], dados["numero"], dados["mes_inicial"],
            dados["imoveis_programados"], dados["imoveis_trabalhados"], **comum,
        )
    if tipo == "LevantamentoLIRAa":
        return LevantamentoLIRAa(
            modulo, date.fromisoformat(dados["data_inicio"]), date.fromisoformat(dados["data_fim"]),
            dados["indice_predial"], dados["indice_breteau"], dados.get("pontos_estrategicos", 0), **comum,
        )
    raise ErroValidacao(f"Tipo de registro desconhecido no arquivo: {tipo}")


# --------------------------------------------------------------- relatórios
def relatorio_para_dict(relatorio: RelatorioQuadrimestral) -> dict:
    return {
        "id": relatorio.id,
        "ano": relatorio.ano,
        "quadrimestre": relatorio.quadrimestre,
        "status": relatorio.status.value,
        "versao": relatorio.versao,
        "destaques": relatorio.destaques,
        "homologado_em": _iso(relatorio.homologado_em),
        "homologado_por": relatorio.homologado_por,
        "justificativas": list(relatorio.justificativas),
    }


def relatorio_de_dict(dados: dict) -> RelatorioQuadrimestral:
    return RelatorioQuadrimestral(
        dados["ano"], dados["quadrimestre"], dados.get("status", "rascunho"),
        dados.get("versao", 1), dados.get("destaques", ""),
        _data_hora(dados.get("homologado_em")), dados.get("homologado_por"),
        dados.get("justificativas", []), id=dados.get("id"),
    )


# -------------------------------------------------------------- importações
def importacao_para_dict(importacao: Importacao) -> dict:
    return {
        "id": importacao.id,
        "nome_arquivo": importacao.nome_arquivo,
        "realizada_por": importacao.realizada_por,
        "status": importacao.status.value,
        "data_hora": _iso(importacao.data_hora),
        "validas": list(importacao.validas),
        "rejeitadas": [list(e) for e in importacao.erros],
    }


def importacao_de_dict(dados: dict) -> Importacao:
    return Importacao(
        dados["nome_arquivo"], dados.get("realizada_por"), dados.get("status", "pendente"),
        _data_hora(dados.get("data_hora")), dados.get("validas", []),
        [tuple(e) for e in dados.get("rejeitadas", [])], id=dados.get("id"),
    )


# ---------------------------------------------------------------- auditoria
def log_para_dict(log: LogAuditoria) -> dict:
    return {
        "id": log.id,
        "data_hora": _iso(log.data_hora),
        "usuario": log.usuario,
        "acao": log.acao,
        "entidade": log.entidade,
        "valor_anterior": log.valor_anterior,
        "valor_novo": log.valor_novo,
    }


def log_de_dict(dados: dict) -> LogAuditoria:
    return LogAuditoria(
        dados["usuario"], dados["acao"], dados["entidade"],
        dados.get("valor_anterior"), dados.get("valor_novo"),
        _data_hora(dados.get("data_hora")), dados.get("id"),
    )
