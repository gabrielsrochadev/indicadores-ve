"""Persistência em arquivo JSON (alteração A04) com backup diário (A10 / RNF11).

RepositorioJSON herda de Repositorio: aproveita todas as operações de
cadastrar, consultar, atualizar e excluir da classe base e implementa só
os dois métodos abstratos, carregar() e salvar().

Gravação segura: o JSON é escrito primeiro num arquivo temporário e só
depois substitui o original. Se o programa cair no meio, o banco anterior
continua inteiro.
"""

from __future__ import annotations

import json
import os
import shutil
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Callable

from ..excecoes import ErroSistema
from ..models import Permissao
from . import serializador as s
from .repositorio import Repositorio

VERSAO_FORMATO = 1


class RepositorioJSON(Repositorio):
    def __init__(
        self,
        caminho: str | Path = "data/banco.json",
        pasta_backup: str | Path | None = None,
        dias_backup: int = 30,
        hoje: Callable[[], date] = date.today,
    ) -> None:
        self.caminho = Path(caminho)
        self.pasta_backup = Path(pasta_backup) if pasta_backup else self.caminho.parent / "backups"
        self.dias_backup = dias_backup
        self._hoje = hoje
        super().__init__()

    # ------------------------------------------------------------- leitura
    def carregar(self) -> None:
        """Lê o arquivo e reconstrói os objetos. Sem arquivo = banco vazio."""
        self.limpar()
        if not self.caminho.exists():
            return
        try:
            dados = json.loads(self.caminho.read_text(encoding="utf-8"))
        except json.JSONDecodeError as erro:
            raise ErroSistema(
                f"O arquivo {self.caminho} está corrompido ({erro}). "
                f"Restaure uma cópia da pasta {self.pasta_backup}."
            ) from None

        # A ordem importa: perfis → usuários → módulos → registros (dependências)
        permissoes: dict[str, Permissao] = {}
        for p in dados.get("perfis", []):
            self.adicionar_perfil(s.perfil_de_dict(p, permissoes))
        for u in dados.get("usuarios", []):
            self.adicionar_usuario(s.usuario_de_dict(u, self.obter_perfil))
        for m in dados.get("modulos", []):
            self.adicionar_modulo(s.modulo_de_dict(m))
        for r in dados.get("registros", []):
            self.salvar_registro(s.registro_de_dict(r, self.obter_modulo, self._usuario_ou_nada))
        for r in dados.get("relatorios", []):
            self.salvar_relatorio(s.relatorio_de_dict(r))
        for i in dados.get("importacoes", []):
            self.salvar_importacao(s.importacao_de_dict(i))
        self.carregar_logs(s.log_de_dict(l) for l in dados.get("logs", []))
        for colecao, valor in dados.get("contadores", {}).items():
            self._ajustar_contador(colecao, valor)

    def _usuario_ou_nada(self, login: str | None):
        if not login:
            return None
        return self._usuarios.get(login)

    # ------------------------------------------------------------ gravação
    def para_dict(self) -> dict:
        return {
            "versao_formato": VERSAO_FORMATO,
            "salvo_em": datetime.now().isoformat(timespec="seconds"),
            "contadores": dict(self._contadores),
            "perfis": [s.perfil_para_dict(p) for p in self.listar_perfis()],
            "usuarios": [s.usuario_para_dict(u) for u in self.listar_usuarios()],
            "modulos": [s.modulo_para_dict(m) for m in self.listar_modulos()],
            "registros": [s.registro_para_dict(r) for r in self.listar_registros()],
            "relatorios": [s.relatorio_para_dict(r) for r in self.listar_relatorios()],
            "importacoes": [s.importacao_para_dict(i) for i in self.listar_importacoes()],
            "logs": [s.log_para_dict(l) for l in self.listar_logs()],
        }

    def salvar(self) -> None:
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        self.fazer_backup()
        temporario = self.caminho.with_suffix(".tmp")
        temporario.write_text(
            json.dumps(self.para_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
        )
        os.replace(temporario, self.caminho)  # troca atômica

    # -------------------------------------------------------------- backup
    def fazer_backup(self) -> Path | None:
        """RNF11: guarda uma cópia por dia e apaga as mais antigas que 30 dias."""
        if not self.caminho.exists():
            return None
        self.pasta_backup.mkdir(parents=True, exist_ok=True)
        hoje = self._hoje()
        destino = self.pasta_backup / f"banco_{hoje.isoformat()}.json"
        if not destino.exists():  # a primeira gravação do dia guarda o estado anterior
            shutil.copy2(self.caminho, destino)
        limite = hoje - timedelta(days=self.dias_backup)
        for arquivo in self.pasta_backup.glob("banco_*.json"):
            try:
                dia = date.fromisoformat(arquivo.stem.removeprefix("banco_"))
            except ValueError:
                continue
            if dia < limite:
                arquivo.unlink()
        return destino

    def __repr__(self) -> str:
        return f"RepositorioJSON(caminho={str(self.caminho)!r})"
