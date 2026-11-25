"""Cria (ou recria) o banco data/banco.json com os dados iniciais.

Uso:
    python scripts/seed.py            # cria o banco se ainda não existir
    python scripts/seed.py --forcar   # apaga o banco atual e recria
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))  # permite rodar sem instalar o pacote

from indicadores_ve.persistence.repositorio_json import RepositorioJSON  # noqa: E402
from indicadores_ve.services.carga_inicial import carregar_dados_iniciais  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Carga inicial do Sistema de Indicadores da VE.")
    parser.add_argument("--banco", default=RAIZ / "data" / "banco.json", type=Path)
    parser.add_argument("--dados", default=RAIZ / "data" / "dados_iniciais.json", type=Path)
    parser.add_argument("--forcar", action="store_true", help="recria o banco mesmo se ele já existir")
    args = parser.parse_args()

    if args.banco.exists() and not args.forcar:
        print(f"O banco {args.banco} já existe. Use --forcar para recriá-lo.")
        return 1

    resumo = carregar_dados_iniciais(RepositorioJSON(args.banco), args.dados)
    print(f"Banco criado em {args.banco}")
    print(f"  {resumo['usuarios']} usuários, {resumo['indicadores']} indicadores, "
          f"{resumo['registros']} registros")
    print("\nConferência RN06 – totais calculados pelo sistema × informados no relatório:")
    for chave, valores in resumo["conferencia"].items():
        marca = "OK" if valores["calculado"] == valores["informado"] else "DIVERGE"
        print(f"  {chave:<24} calculado {valores['calculado']:>6}   "
              f"informado {valores['informado']!s:>6}   {marca}")
    print("\nUsuários de demonstração: admin / coordenador / gestor / digitador "
          "(senhas no README.md)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
