"""Ponto de entrada: python -m indicadores_ve  (ou python main.py na raiz do projeto)."""

from __future__ import annotations

import argparse
from pathlib import Path

from .cli import Aplicacao
from .excecoes import ErroSistema
from .persistence import RepositorioJSON
from .services import Sistema
from .services.carga_inicial import carregar_dados_iniciais


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Sistema de Indicadores da VE de Balsas-MA")
    parser.add_argument("--banco", default="data/banco.json", type=Path, help="arquivo JSON do banco")
    parser.add_argument("--dados", default="data/dados_iniciais.json", type=Path,
                        help="dados usados se o banco ainda não existir")
    args = parser.parse_args(argv)

    repositorio = RepositorioJSON(args.banco)
    try:
        if not args.banco.exists():
            print(f"Banco não encontrado. Criando a partir de {args.dados}...")
            carregar_dados_iniciais(repositorio, args.dados)
        repositorio.carregar()
    except (ErroSistema, FileNotFoundError) as erro:
        print(f"[!] Não foi possível abrir o banco: {erro}")
        return 1

    Aplicacao(Sistema(repositorio)).executar()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
