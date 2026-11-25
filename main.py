"""Atalho para iniciar o sistema sem instalar o pacote:  python main.py"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from indicadores_ve.__main__ import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
